from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.workflow import WorkflowStatus
from app.schemas.task import TaskResponse


class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = None
    creator_id: str


class WorkflowCreate(WorkflowBase):
    tasks: List["TaskCreate"] = []


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[WorkflowStatus] = None


class WorkflowResponse(WorkflowBase):
    id: int
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    tasks: List[TaskResponse] = []
    status_url: Optional[str] = None

    class Config:
        from_attributes = True


# Import here to avoid circular imports
from app.schemas.task import TaskCreate
WorkflowCreate.model_rebuild()
