from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.task import TaskStatus


class TaskBase(BaseModel):
    name: str
    description: Optional[str] = None
    script_content: str
    requirements: List[str] = []
    order: int = 0


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    script_content: Optional[str] = None
    requirements: Optional[List[str]] = None
    order: Optional[int] = None
    status: Optional[TaskStatus] = None


class TaskResponse(TaskBase):
    id: int
    workflow_id: int
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    celery_task_id: Optional[str] = None
    output: Optional[str] = None
    error_message: Optional[str] = None
    task_outputs: Optional[dict] = None

    class Config:
        from_attributes = True
