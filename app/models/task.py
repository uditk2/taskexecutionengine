from sqlalchemy import Column, Integer, String, DateTime, Text, Enum as SQLEnum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from app.core.database import Base


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    script_content = Column(Text, nullable=False)
    requirements = Column(JSON, default=list)  # List of pip packages
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, index=True)
    order = Column(Integer, default=0)  # Execution order within workflow
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    celery_task_id = Column(String(255), nullable=True, index=True)
    output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationship to workflow
    workflow = relationship("Workflow", back_populates="tasks")
