from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime
from app.core.database import get_db
from app.models.workflow import Workflow, WorkflowStatus
from app.models.task import Task
from app.schemas.workflow import WorkflowCreate, WorkflowResponse, WorkflowUpdate
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.tasks.workflow_tasks import execute_workflow
from app.celery_app import celery_app

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/", response_model=WorkflowResponse)
async def create_workflow(
    workflow_data: WorkflowCreate,
    mode: str = Query("create", description="Execution mode: 'create' (create only) or 'run' (create and execute immediately)"),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    if mode not in ["create", "run"]:
        raise HTTPException(status_code=400, detail="Mode must be 'create' or 'run'")
    
    workflow = Workflow(
        name=workflow_data.name,
        description=workflow_data.description,
        creator_id=workflow_data.creator_id
    )
    db.add(workflow)
    await db.flush()
    
    for task_data in workflow_data.tasks:
        task = Task(
            workflow_id=workflow.id,
            name=task_data.name,
            description=task_data.description,
            script_content=task_data.script_content,
            requirements=task_data.requirements,
            order=task_data.order
        )
        db.add(task)
    
    await db.commit()
    await db.refresh(workflow)
    
    if mode == "run":
        task_result = execute_workflow.delay(workflow.id)
        workflow.celery_task_id = task_result.id
        workflow.status = WorkflowStatus.RUNNING
        await db.commit()
    
    result = await db.execute(
        select(Workflow).options(selectinload(Workflow.tasks)).where(Workflow.id == workflow.id)
    )
    workflow_with_tasks = result.scalar_one()
    
    base_url = str(request.base_url) if request else "http://localhost:8000/"
    status_url = f"{base_url.rstrip('/')}/api/v1/workflows/{workflow.id}/status"
    
    response_data = WorkflowResponse.from_orm(workflow_with_tasks)
    response_data.status_url = status_url
    
    return response_data


@router.get("/", response_model=List[WorkflowResponse])
async def list_workflows(
    status: Optional[WorkflowStatus] = None,
    creator_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Workflow).options(selectinload(Workflow.tasks))
    if status:
        query = query.where(Workflow.status == status)
    if creator_id:
        query = query.where(Workflow.creator_id == creator_id)
    query = query.offset(skip).limit(limit).order_by(Workflow.created_at.desc())
    result = await db.execute(query)
    workflows = result.scalars().all()
    base_url = str(request.base_url) if request else "http://localhost:8000/"
    response_workflows = []
    for workflow in workflows:
        response_data = WorkflowResponse.from_orm(workflow)
        response_data.status_url = f"{base_url.rstrip('/')}/api/v1/workflows/{workflow.id}/status"
        response_workflows.append(response_data)
    return response_workflows


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: int, request: Request = None, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Workflow).options(selectinload(Workflow.tasks)).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    base_url = str(request.base_url) if request else "http://localhost:8000/"
    response_data = WorkflowResponse.from_orm(workflow)
    response_data.status_url = f"{base_url.rstrip('/')}/api/v1/workflows/{workflow.id}/status"
    return response_data


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    workflow_update: WorkflowUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Workflow).options(selectinload(Workflow.tasks)).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    for field, value in workflow_update.dict(exclude_unset=True).items():
        setattr(workflow, field, value)
    await db.commit()
    await db.refresh(workflow)
    base_url = str(request.base_url) if request else "http://localhost:8000/"
    response_data = WorkflowResponse.from_orm(workflow)
    response_data.status_url = f"{base_url.rstrip('/')}/api/v1/workflows/{workflow.id}/status"
    return response_data


@router.post("/{workflow_id}/execute")
async def execute_workflow_endpoint(workflow_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Workflow is already running")
    task_result = execute_workflow.delay(workflow_id)
    workflow.celery_task_id = task_result.id
    workflow.status = WorkflowStatus.RUNNING
    await db.commit()
    return {"message": "Workflow execution started", "celery_task_id": task_result.id}


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if workflow can be cancelled based on its status
    if workflow.status == WorkflowStatus.COMPLETED or workflow.status == WorkflowStatus.CANCELLED or workflow.status == WorkflowStatus.FAILED:
        # Already in a terminal state, just return success
        return {"message": "Workflow is already in a completed state", "status": workflow.status}
    
    # Cancel only if there's a task_id to revoke
    if workflow.celery_task_id:
        try:
            celery_app.control.revoke(workflow.celery_task_id, terminate=True)
        except Exception as e:
            # Log the error but continue with status change
            print(f"Error revoking Celery task {workflow.celery_task_id}: {str(e)}")
    
    # Update status regardless of original status
    workflow.status = WorkflowStatus.CANCELLED
    await db.commit()
    return {"message": "Workflow cancelled"}


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete running workflow")
    await db.delete(workflow)
    await db.commit()
    return {"message": "Workflow deleted"}


@router.get("/{workflow_id}/status")
async def get_workflow_status(workflow_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Workflow).options(selectinload(Workflow.tasks)).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        "id": workflow.id,
        "name": workflow.name,
        "status": workflow.status,
        "started_at": workflow.started_at,
        "completed_at": workflow.completed_at,
        "error_message": workflow.error_message,
        "tasks": [
            {
                "id": task.id,
                "name": task.name,
                "status": task.status,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "error_message": task.error_message,
                "task_outputs": task.task_outputs or {}
            } for task in sorted(workflow.tasks, key=lambda t: t.order)
        ]
    }


@router.post("/{workflow_id}/schedule")
async def schedule_workflow(
    workflow_id: int,
    schedule_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """Enable scheduling for a workflow"""
    cron_expression = schedule_data.get("cron_expression")
    timezone = schedule_data.get("timezone", "UTC")
    
    # Validate cron expression
    if not cron_expression:
        raise HTTPException(status_code=400, detail="Cron expression is required")
    
    cron_parts = cron_expression.split()
    if len(cron_parts) != 5:
        raise HTTPException(
            status_code=400, 
            detail="Cron expression must have 5 parts (minute hour day month day_of_week)"
        )
    
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Calculate next run time
    try:
        from croniter import croniter
        import pytz
        
        tz = pytz.timezone(timezone)
        # Use current time in the workflow's timezone as base
        current_time_tz = datetime.now(tz)
        # Create croniter with timezone-aware current time
        cron = croniter(cron_expression, current_time_tz)
        # Get next run time in the workflow's timezone
        next_run_tz = cron.get_next(datetime)
        # Convert to UTC for storage (consistent with other datetime fields)
        next_run_utc = next_run_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # Update workflow with scheduling info
        workflow.is_scheduled = True
        workflow.cron_expression = cron_expression
        workflow.timezone = timezone
        workflow.next_run_at = next_run_utc
        
        await db.commit()
        
        # Register with Celery Beat
        await register_workflow_schedule(workflow)
        
        return {
            "message": "Workflow scheduled successfully",
            "cron_expression": cron_expression,
            "timezone": timezone,
            "next_run_at": next_run_utc
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression or timezone: {str(e)}")


@router.delete("/{workflow_id}/schedule")
async def unschedule_workflow(workflow_id: int, db: AsyncSession = Depends(get_db)):
    """Disable scheduling for a workflow"""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    if not workflow.is_scheduled:
        raise HTTPException(status_code=400, detail="Workflow is not scheduled")
    
    # Remove from Celery Beat
    await unregister_workflow_schedule(workflow)
    
    # Update workflow
    workflow.is_scheduled = False
    workflow.cron_expression = None
    workflow.next_run_at = None
    
    await db.commit()
    
    return {"message": "Workflow unscheduled successfully"}


@router.get("/{workflow_id}/schedule")
async def get_workflow_schedule(workflow_id: int, db: AsyncSession = Depends(get_db)):
    """Get scheduling information for a workflow"""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return {
        "workflow_id": workflow.id,
        "is_scheduled": workflow.is_scheduled,
        "cron_expression": workflow.cron_expression,
        "timezone": workflow.timezone,
        "next_run_at": workflow.next_run_at,
        "last_run_at": workflow.last_run_at,
        "run_count": workflow.run_count
    }


async def register_workflow_schedule(workflow: Workflow):
    """Register a workflow with Celery Beat"""
    if workflow.is_scheduled and workflow.cron_expression:
        from celery.schedules import crontab
        
        task_name = f"scheduled_workflow_{workflow.id}"
        cron_parts = workflow.cron_expression.split()
        
        celery_app.conf.beat_schedule[task_name] = {
            'task': 'app.tasks.workflow_tasks.execute_scheduled_workflow',
            'schedule': crontab(
                minute=cron_parts[0],
                hour=cron_parts[1],
                day_of_month=cron_parts[2],
                month_of_year=cron_parts[3],
                day_of_week=cron_parts[4]
            ),
            'args': (workflow.id,),
            'options': {'timezone': workflow.timezone}
        }


async def unregister_workflow_schedule(workflow: Workflow):
    """Unregister a workflow from Celery Beat"""
    task_name = f"scheduled_workflow_{workflow.id}"
    if task_name in celery_app.conf.beat_schedule:
        del celery_app.conf.beat_schedule[task_name]


