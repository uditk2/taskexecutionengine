from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.workflow import Workflow, WorkflowStatus
from app.models.task import Task
from app.schemas.workflow import WorkflowCreate, WorkflowResponse, WorkflowUpdate
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
    if workflow.status != WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Workflow is not running")
    if workflow.celery_task_id:
        celery_app.control.revoke(workflow.celery_task_id, terminate=True)
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
                "error_message": task.error_message
            } for task in sorted(workflow.tasks, key=lambda t: t.order)
        ]
    }