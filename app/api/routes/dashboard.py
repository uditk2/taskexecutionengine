from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from pathlib import Path
from typing import Optional
from app.core.database import get_db
from app.models.workflow import Workflow, WorkflowStatus
from app.models.task import Task, TaskStatus
from app.core.config import settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")


@router.get("/active-tasks", response_class=HTMLResponse)
async def active_tasks_dashboard(
    request: Request,
    poll_interval: int = Query(default=15, ge=5, le=60),
    db: AsyncSession = Depends(get_db)
):
    """Dashboard showing all active (pending and running) tasks"""
    # Get active tasks (pending and running)
    active_tasks_query = select(Task).options(
        selectinload(Task.workflow)
    ).where(
        Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
    ).order_by(Task.created_at.desc())
    
    active_tasks_result = await db.execute(active_tasks_query)
    active_tasks = active_tasks_result.scalars().all()
    
    # Get active workflows (pending and running)
    active_workflows_query = select(Workflow).options(
        selectinload(Workflow.tasks)
    ).where(
        Workflow.status.in_([WorkflowStatus.PENDING, WorkflowStatus.RUNNING])
    ).order_by(Workflow.created_at.desc())
    
    active_workflows_result = await db.execute(active_workflows_query)
    active_workflows = active_workflows_result.scalars().all()
    
    # Get task statistics by status
    task_stats_query = select(
        Task.status,
        func.count(Task.id).label('count')
    ).group_by(Task.status)
    
    task_stats_result = await db.execute(task_stats_query)
    task_stats = {row.status: row.count for row in task_stats_result}
    
    # Get workflow statistics by status
    workflow_stats_query = select(
        Workflow.status,
        func.count(Workflow.id).label('count')
    ).group_by(Workflow.status)
    
    workflow_stats_result = await db.execute(workflow_stats_query)
    workflow_stats = {row.status: row.count for row in workflow_stats_result}
    
    return templates.TemplateResponse(
        "pages/active_tasks.html",
        {
            "request": request,
            "layout": "dashboard",
            "navbar": "side_fixed",
            "title": "Active Tasks Dashboard",
            "settings": settings,
            "active_tasks": active_tasks,
            "active_workflows": active_workflows,
            "task_stats": task_stats,
            "workflow_stats": workflow_stats,
            "poll_interval": max(poll_interval, settings.MIN_POLL_INTERVAL)
        }
    )


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    poll_interval: int = Query(default=15, ge=5, le=60),
    db: AsyncSession = Depends(get_db)
):
    """Main dashboard page with workflow overview"""
    # Get workflow statistics
    stats_query = select(
        Workflow.status,
        func.count(Workflow.id).label('count')
    ).group_by(Workflow.status)
    
    stats_result = await db.execute(stats_query)
    stats = {row.status: row.count for row in stats_result}
    
    # Get recent workflows
    recent_workflows_query = select(Workflow).options(
        selectinload(Workflow.tasks)
    ).order_by(Workflow.created_at.desc()).limit(10)
    
    recent_result = await db.execute(recent_workflows_query)
    recent_workflows = recent_result.scalars().all()
    
    return templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "layout": "dashboard",
            "navbar": "side_fixed",
            "title": "Task Execution Dashboard",
            "settings": settings,
            "stats": stats,
            "recent_workflows": recent_workflows,
            "poll_interval": max(poll_interval, settings.MIN_POLL_INTERVAL)
        }
    )


@router.get("/workflow/{workflow_id}", response_class=HTMLResponse)
async def workflow_detail(
    request: Request,
    workflow_id: int,
    poll_interval: int = Query(default=15, ge=5, le=60),
    db: AsyncSession = Depends(get_db)
):
    """Detailed workflow monitoring page"""
    result = await db.execute(
        select(Workflow).options(selectinload(Workflow.tasks)).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        return templates.TemplateResponse(
            "pages/error.html",
            {
                "request": request,
                "layout": "default",
                "title": "Workflow Not Found",
                "error_message": f"Workflow {workflow_id} not found"
            },
            status_code=404
        )
    
    return templates.TemplateResponse(
        "pages/workflow_detail.html",
        {
            "request": request,
            "layout": "dashboard",
            "navbar": "side_fixed",
            "title": f"Workflow: {workflow.name}",
            "settings": settings,
            "workflow": workflow,
            "poll_interval": max(poll_interval, settings.MIN_POLL_INTERVAL)
        }
    )


@router.get("/api/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """API endpoint for dashboard statistics"""
    # Workflow stats
    workflow_stats_query = select(
        Workflow.status,
        func.count(Workflow.id).label('count')
    ).group_by(Workflow.status)
    
    workflow_stats_result = await db.execute(workflow_stats_query)
    workflow_stats = {row.status: row.count for row in workflow_stats_result}
    
    # Task stats
    task_stats_query = select(
        Task.status,
        func.count(Task.id).label('count')
    ).group_by(Task.status)
    
    task_stats_result = await db.execute(task_stats_query)
    task_stats = {row.status: row.count for row in task_stats_result}
    
    return {
        "workflow_stats": workflow_stats,
        "task_stats": task_stats
    }