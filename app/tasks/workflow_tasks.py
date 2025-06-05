from datetime import datetime, timedelta
from typing import List, Dict, Any
from celery import current_task, chain
from sqlalchemy.orm import Session
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.workflow import Workflow, WorkflowStatus
from app.models.task import Task, TaskStatus
from app.core.config import settings
from app.executors import ExecutorFactory
from croniter import croniter
import pytz


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
        workflow.started_at = datetime.now()
        workflow.celery_task_id = self.request.id
        db.commit()
        
        # Get tasks ordered by execution order
        tasks = db.query(Task).filter(Task.workflow_id == workflow_id).order_by(Task.order).all()
        
        if not tasks:
            # No tasks to execute, mark as completed
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.utcnow()
            db.commit()
            return {"status": "completed", "workflow_id": workflow_id}
        
        # Create a chain of tasks to execute sequentially
        task_chain = []
        for task in tasks:
            task_chain.append(execute_task.s(task.id))
        
        # Add workflow completion task at the end
        task_chain.append(complete_workflow.s(workflow_id))
        
        # Execute the chain
        chain_result = chain(*task_chain).apply_async()
        
        # Update workflow with chain task ID for tracking
        workflow.celery_task_id = chain_result.id
        db.commit()
        
        return {"status": "started", "workflow_id": workflow_id, "chain_id": chain_result.id}
        
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
def execute_task(self, task_id: int, executor_name: str = None, previous_result=None):
    """Execute a single task using the specified executor"""
    db = SessionLocal()
    executor = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Check if previous task failed (when chaining)
        if previous_result and isinstance(previous_result, dict):
            if previous_result.get("status") == "failed":
                # Previous task failed, mark this task as failed too
                task.status = TaskStatus.FAILED
                task.error_message = f"Previous task failed: {previous_result.get('error_message', 'Unknown error')}"
                task.completed_at = datetime.utcnow()
                db.commit()
                return {
                    "status": "failed",
                    "task_id": task_id,
                    "error_message": task.error_message
                }
        
        # Update task status
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.celery_task_id = self.request.id
        db.commit()
        
        # Get previous tasks' outputs for data pipeline
        previous_tasks = db.query(Task).filter(
            Task.workflow_id == task.workflow_id,
            Task.order < task.order,
            Task.status == TaskStatus.COMPLETED
        ).order_by(Task.order).all()
        
        # Create executor
        executor_name = executor_name or settings.DEFAULT_EXECUTOR
        executor = ExecutorFactory.create_executor(executor_name)
        
        # Execute task with previous outputs available
        result = executor.execute(
            script_content=task.script_content,
            requirements=task.requirements or [],
            timeout=settings.TASK_TIMEOUT,
            previous_outputs=[{
                'task_name': prev_task.name,
                'task_order': prev_task.order,
                'outputs': prev_task.task_outputs or {},
                'raw_output': prev_task.output
            } for prev_task in previous_tasks]
        )
        
        # Update task with results
        if result.success:
            task.status = TaskStatus.COMPLETED
            task.output = result.output
            # Extract structured outputs from task result
            task.task_outputs = getattr(result, 'task_outputs', {})
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
            "execution_time": result.execution_time,
            "task_outputs": task.task_outputs
        }
    except Exception as e:
        if 'task' in locals():
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()
        return {
            "status": "failed",
            "task_id": task_id,
            "error_message": str(e)
        }
    finally:
        if executor:
            executor.cleanup()
        db.close()


@celery_app.task
def complete_workflow(previous_result, workflow_id: int):
    """Complete a workflow after all tasks are done"""
    db = SessionLocal()
    try:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            return {"status": "error", "message": f"Workflow {workflow_id} not found"}
        
        # Check if the last task failed
        if isinstance(previous_result, dict) and previous_result.get("status") == "failed":
            workflow.status = WorkflowStatus.FAILED
            workflow.error_message = f"Task execution failed: {previous_result.get('error_message', 'Unknown error')}"
        else:
            # Check if any task in the workflow failed
            failed_tasks = db.query(Task).filter(
                Task.workflow_id == workflow_id,
                Task.status == TaskStatus.FAILED
            ).first()
            
            if failed_tasks:
                workflow.status = WorkflowStatus.FAILED
                workflow.error_message = "One or more tasks failed"
            else:
                workflow.status = WorkflowStatus.COMPLETED
        
        workflow.completed_at = datetime.utcnow()
        db.commit()
        
        return {
            "status": workflow.status.value,
            "workflow_id": workflow_id,
            "completed_at": workflow.completed_at.isoformat()
        }
        
    except Exception as e:
        if 'workflow' in locals():
            workflow.status = WorkflowStatus.FAILED
            workflow.error_message = str(e)
            workflow.completed_at = datetime.utcnow()
            db.commit()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task
def execute_scheduled_workflow(workflow_id: int):
    """Execute a scheduled workflow and update scheduling metadata"""
    db = SessionLocal()
    try:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            return {"status": "error", "message": f"Workflow {workflow_id} not found"}
        
        if not workflow.is_scheduled:
            return {"status": "skipped", "message": "Workflow is not scheduled"}
        
        # Update run tracking
        workflow.run_count += 1
        workflow.last_run_at = datetime.utcnow()
        
        # Calculate next run time
        try:
            tz = pytz.timezone(workflow.timezone)
            cron = croniter(workflow.cron_expression, datetime.now(tz))
            workflow.next_run_at = cron.get_next(datetime)
        except Exception as e:
            print(f"Error calculating next run time: {e}")
        
        db.commit()
        
        # Execute the workflow
        execute_workflow.delay(workflow_id)
        
        return {
            "status": "started",
            "workflow_id": workflow_id,
            "run_count": workflow.run_count
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task
def check_and_execute_scheduled_workflows():
    """Check for scheduled workflows that are due to run and execute them"""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        
        # Find workflows that are scheduled and due to run
        due_workflows = db.query(Workflow).filter(
            Workflow.is_scheduled == True,
            Workflow.next_run_at <= now,
            Workflow.status.in_([WorkflowStatus.PENDING, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED])
        ).all()
        
        executed_count = 0
        for workflow in due_workflows:
            try:
                # Execute the scheduled workflow
                execute_scheduled_workflow.delay(workflow.id)
                executed_count += 1
            except Exception as e:
                print(f"Error scheduling workflow {workflow.id}: {e}")
        
        return {
            "status": "completed",
            "checked_at": now.isoformat(),
            "executed_count": executed_count
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
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
