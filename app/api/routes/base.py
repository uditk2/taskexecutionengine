from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.config import settings
from app.core.database import get_db
from app.models.task import Task
from app.executors import ExecutorFactory

def escapejs_filter(value):
    """Custom Jinja2 filter to escape JavaScript strings"""
    if value is None:
        return ""
    return json.dumps(str(value))[1:-1]  # Remove the surrounding quotes

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent.parent / "templates")
templates.env.filters['escapejs'] = escapejs_filter

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Redirect to the active tasks dashboard
    return RedirectResponse(url="/dashboard/active-tasks", status_code=status.HTTP_302_FOUND)

@router.get("/task/{task_id}/edit", response_class=HTMLResponse)
async def edit_task(request: Request, task_id: int, db: AsyncSession = Depends(get_db)):
    """Task edit page"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return templates.TemplateResponse("pages/task_edit.html", {
        "request": request,
        "task": task,
        "settings": settings
    })

@router.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}

@router.get("/diagnostics", tags=["debug"])
async def diagnostics():
    """Diagnostic information for debugging executor and configuration issues"""
    try:
        # Get available executors
        available_executors = ExecutorFactory.list_executors()
        
        # Test each executor
        executor_status = {}
        for executor_name in available_executors:
            try:
                executor = ExecutorFactory.create_executor(executor_name)
                executor_status[executor_name] = {
                    "available": True,
                    "name": executor.name,
                    "class": executor.__class__.__name__,
                    "error": None
                }
                executor.cleanup()  # Clean up test instance
            except Exception as e:
                executor_status[executor_name] = {
                    "available": False,
                    "name": executor_name,
                    "class": "Unknown",
                    "error": str(e)
                }
        
        # Configuration info
        config_info = {
            "DEFAULT_EXECUTOR": settings.DEFAULT_EXECUTOR,
            "TASK_TIMEOUT": settings.TASK_TIMEOUT,
            "VENV_BASE_PATH": settings.VENV_BASE_PATH,
            "DOCKER_IMAGE": settings.DOCKER_IMAGE,
        }
        
        return {
            "status": "ok",
            "configuration": config_info,
            "available_executors": available_executors,
            "executor_status": executor_status,
            "default_executor_available": settings.DEFAULT_EXECUTOR in available_executors,
            "recommended_action": (
                "Configuration looks good!" if settings.DEFAULT_EXECUTOR in available_executors 
                else f"Default executor '{settings.DEFAULT_EXECUTOR}' not available. Available: {available_executors}"
            )
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "available_executors": [],
            "executor_status": {},
            "default_executor_available": False,
            "recommended_action": f"Critical error: {str(e)}"
        }
