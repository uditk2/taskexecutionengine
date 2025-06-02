from datetime import datetime, timedelta
from typing import List, Dict, Any
from celery import current_task
from sqlalchemy.orm import Session
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.workflow import Workflow, WorkflowStatus
from app.models.task import Task, TaskStatus
from app.core.config import settings
from app.executors import ExecutorFactory


@celery_app.task(bind=True)
def execute_workflow(self, workflow_id: int):
    """Execute a complete workflow"""
    db = SessionLocal()
    try:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        # Update workflow status
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.utcnow()
        workflow.celery_task_id = self.request.id
        db.commit()
        
        # Get tasks ordered by execution order
        tasks = db.query(Task).filter(Task.workflow_id == workflow_id).order_by(Task.order).all()
        
        # Execute tasks sequentially
        for task in tasks:
            try:
                result = execute_task.delay(task.id)
                task.celery_task_id = result.id
                db.commit()
                
                # Wait for task completion
                task_result = result.get(timeout=settings.TASK_TIMEOUT)
                
                # Refresh task from database
                db.refresh(task)
                
                if task.status == TaskStatus.FAILED:
                    raise Exception(f"Task {task.name} failed: {task.error_message}")
            except Exception as e:
                # Mark workflow as failed
                workflow.status = WorkflowStatus.FAILED
                workflow.error_message = str(e)
                workflow.completed_at = datetime.utcnow()
                db.commit()
                raise
        
        # Mark workflow as completed
        workflow.status = WorkflowStatus.COMPLETED
        workflow.completed_at = datetime.utcnow()
        db.commit()
        
        return {"status": "completed", "workflow_id": workflow_id}
    except Exception as e:
        if 'workflow' in locals():
            workflow.status = WorkflowStatus.FAILED
            workflow.error_message = str(e)
            workflow.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def execute_task(self, task_id: int, executor_name: str = None):
    """Execute a single task using the specified executor"""
    db = SessionLocal()
    executor = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.celery_task_id = self.request.id
        db.commit()
        
        # Create executor
        executor_name = executor_name or settings.DEFAULT_EXECUTOR
        executor = ExecutorFactory.create_executor(executor_name)
        
        # Execute task
        result = executor.execute(
            script_content=task.script_content,
            requirements=task.requirements or [],
            timeout=settings.TASK_TIMEOUT
        )
        
        # Update task with results
        if result.success:
            task.status = TaskStatus.COMPLETED
            task.output = result.output
        else:
            task.status = TaskStatus.FAILED
            task.error_message = result.error_message
            task.output = result.output
        
        task.completed_at = datetime.utcnow()
        db.commit()
        
        return {
            "status": "completed" if result.success else "failed",
            "task_id": task_id,
            "output": result.output,
            "error_message": result.error_message,
            "execution_time": result.execution_time
        }
    except Exception as e:
        if 'task' in locals():
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        if executor:
            executor.cleanup()
        db.close()


@celery_app.task
def cleanup_old_tasks():
    """Clean up old completed/failed tasks and workflows"""
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=settings.CLEANUP_DAYS)
        
        old_tasks = db.query(Task).filter(
            Task.completed_at < cutoff_date,
            Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
        ).all()
        
        for task in old_tasks:
            db.delete(task)
        
        old_workflows = db.query(Workflow).filter(
            Workflow.completed_at < cutoff_date,
            Workflow.status.in_([WorkflowStatus.COMPLETED, WorkflowStatus.FAILED])
        ).all()
        
        for workflow in old_workflows:
            db.delete(workflow)
        
        db.commit()
        return f"Cleaned up {len(old_tasks)} tasks and {len(old_workflows)} workflows"
    finally:
        db.close()
