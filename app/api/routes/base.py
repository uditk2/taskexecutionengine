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
