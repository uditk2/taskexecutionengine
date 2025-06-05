from sqlalchemy import Column, Integer, String, DateTime, Text, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
from app.core.database import Base


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    creator_id = Column(String(255), nullable=False, index=True)
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.PENDING, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    celery_task_id = Column(String(255), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    
    # Scheduling-related columns
    is_scheduled = Column(Boolean, default=False, nullable=False, index=True)
    cron_expression = Column(String(255), nullable=True)
    timezone = Column(String(100), default="UTC", nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    run_count = Column(Integer, default=0, nullable=False)
    
    # Relationship to tasks
    tasks = relationship("Task", back_populates="workflow", cascade="all, delete-orphan")
