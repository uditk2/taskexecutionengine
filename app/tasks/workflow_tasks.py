from datetime import datetime, timedelta
from typing import List, Dict, Any

from celery import chain
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.workflow import Workflow, WorkflowStatus
from app.models.task import Task, TaskStatus
from app.core.config import settings
from app.executors import ExecutorFactory
from croniter import croniter
import pytz

# Notification system
from app.notifications.tasks import trigger_notification
from app.notifications.models import (
    NotificationEvent,
    NotificationPriority,
)


# --------------------------------------------------------------------------------------
# WORKFLOW DRIVER
# --------------------------------------------------------------------------------------

@celery_app.task(bind=True)
def execute_workflow(self, workflow_id: int):
    """Entry‑point task that spawns the task‑chain for a workflow."""
    db: Session = SessionLocal()
    try:
        workflow: Workflow | None = (
            db.query(Workflow).filter(Workflow.id == workflow_id).first()
        )
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # ------------------------------------------------------------------
        # Bootstrap bookkeeping
        # ------------------------------------------------------------------
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.utcnow()
        workflow.celery_task_id = self.request.id
        db.commit()

        _notify_workflow(
            NotificationEvent.WORKFLOW_STARTED,
            workflow,
            NotificationPriority.NORMAL,
        )

        # ------------------------------------------------------------------
        # Build execution chain
        # ------------------------------------------------------------------
        tasks: list[Task] = (
            db.query(Task)
            .filter(Task.workflow_id == workflow_id)
            .order_by(Task.order)
            .all()
        )
        if not tasks:
            # Nothing to do
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.utcnow()
            db.commit()
            _notify_workflow(
                NotificationEvent.WORKFLOW_COMPLETED,
                workflow,
                NotificationPriority.NORMAL,
            )
            return {"status": "completed", "workflow_id": workflow_id}

        # Celery injects the previous result *before* the signature params.
        # We therefore seed the first task with a dummy `None` so its
        # positional layout is (previous_result, task_id).
        task_sigs: list = []
        for idx, t in enumerate(tasks):
            if idx == 0:
                task_sigs.append(execute_task.s(None, t.id))
            else:
                task_sigs.append(execute_task.s(t.id))

        # Happy‑path chain – the last link marks completion
        main_chain = chain(*task_sigs) | complete_workflow.s(workflow_id)

        # Schedule, but also attach the same finaliser on error‑path
        chain_result = main_chain.apply_async(
            link_error=complete_workflow.s(workflow_id)
        )

        workflow.celery_task_id = chain_result.id
        db.commit()
        return {
            "status": "started",
            "workflow_id": workflow_id,
            "chain_id": chain_result.id,
        }

    except Exception as exc:
        if "workflow" in locals():
            workflow.status = WorkflowStatus.FAILED
            workflow.error_message = str(exc)
            workflow.completed_at = datetime.utcnow()
            db.commit()
            _notify_workflow(
                NotificationEvent.WORKFLOW_FAILED,
                workflow,
                NotificationPriority.HIGH,
                error_message=str(exc),
            )
        raise
    finally:
        db.close()


# --------------------------------------------------------------------------------------
# TASK EXECUTOR
# --------------------------------------------------------------------------------------

@celery_app.task(bind=True)
def execute_task(
    self,
    previous_result: dict | None,
    task_id: int,
    executor_name: str = "virtualenv",
):
    """Execute a single Task model instance.

    When called through a Celery `chain`, `previous_result` will contain the
    return‑value of the upstream task.
    """
    db: Session = SessionLocal()
    executor = None
    try:
        # ------------------------------------------------------------------
        # Short‑circuit if upstream task failed
        # ------------------------------------------------------------------
        if previous_result and isinstance(previous_result, dict):
            if previous_result.get("status") == "failed":
                return _fail_immediately(
                    db,
                    task_id,
                    f"Upstream task failed: {previous_result.get('error_message')}",
                )

        task: Task | None = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        workflow: Workflow | None = (
            db.query(Workflow).filter(Workflow.id == task.workflow_id).first()
        )
        workflow_name = workflow.name if workflow else f"Workflow {task.workflow_id}"

        # Mark RUNNING
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.celery_task_id = self.request.id
        db.commit()
        _notify_task(
            NotificationEvent.TASK_STARTED,
            task,
            workflow_name,
            NotificationPriority.LOW,
        )

        # Gather previous outputs for pipeline
        prev_tasks = (
            db.query(Task)
            .filter(
                Task.workflow_id == task.workflow_id,
                Task.order < task.order,
                Task.status == TaskStatus.COMPLETED,
            )
            .order_by(Task.order)
            .all()
        )

        previous_outputs = [
            {
                "task_name": pt.name,
                "task_order": pt.order,
                "outputs": pt.task_outputs or {},
                "raw_output": pt.output,
            }
            for pt in prev_tasks
        ]

        # Always use the virtualenv executor
        executor = ExecutorFactory.create_executor("virtualenv")
        result = executor.execute(
            script_content=task.script_content,
            requirements=task.requirements or [],
            timeout=settings.TASK_TIMEOUT,
            previous_outputs=previous_outputs,
        )

        # ------------------------------------------------------------------
        # Persist outcome
        # ------------------------------------------------------------------
        task.completed_at = datetime.utcnow()
        if result.success:
            task.status = TaskStatus.COMPLETED
            task.output = result.output
            task.task_outputs = getattr(result, "task_outputs", {})
            db.commit()
            _notify_task(
                NotificationEvent.TASK_COMPLETED,
                task,
                workflow_name,
                NotificationPriority.NORMAL,
                metadata={
                    "execution_time": result.execution_time,
                    "output_size": len(result.output or ""),
                },
            )
            return {
                "status": "completed",
                "task_id": task_id,
                "output": result.output,
                "execution_time": result.execution_time,
                "task_outputs": task.task_outputs,
            }
        else:
            task.status = TaskStatus.FAILED
            task.error_message = result.error_message
            task.output = result.output
            db.commit()
            _notify_task(
                NotificationEvent.TASK_FAILED,
                task,
                workflow_name,
                NotificationPriority.HIGH,
                error_message=result.error_message,
                metadata={"execution_time": result.execution_time},
            )
            return {
                "status": "failed",
                "task_id": task_id,
                "error_message": result.error_message,
            }

    except Exception as exc:
        return _fail_immediately(db, task_id, str(exc))
    finally:
        if executor:
            executor.cleanup()
        db.close()


# --------------------------------------------------------------------------------------
# FINALISE WORKFLOW
# --------------------------------------------------------------------------------------

@celery_app.task(bind=True)
def complete_workflow(self, previous_result, workflow_id: int):
    """Mark the workflow as COMPLETED or FAILED once all tasks end."""
    db: Session = SessionLocal()
    try:
        workflow: Workflow | None = (
            db.query(Workflow).filter(Workflow.id == workflow_id).first()
        )
        if not workflow:
            return {"status": "error", "message": f"Workflow {workflow_id} not found"}

        # Quick exit if already FINAL
        if workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
            return {"status": workflow.status.value, "workflow_id": workflow_id}

        # If previous_result contains a failure bubble up
        if previous_result and isinstance(previous_result, dict):
            if previous_result.get("status") == "failed":
                workflow.status = WorkflowStatus.FAILED
                workflow.error_message = previous_result.get("error_message")
        else:
            # Inspect children states
            tasks = db.query(Task).filter(Task.workflow_id == workflow_id).all()
            if any(t.status == TaskStatus.FAILED for t in tasks):
                workflow.status = WorkflowStatus.FAILED
                workflow.error_message = "One or more tasks failed"
            elif all(t.status == TaskStatus.COMPLETED for t in tasks):
                workflow.status = WorkflowStatus.COMPLETED

        workflow.completed_at = datetime.utcnow()
        db.commit()

        if workflow.status == WorkflowStatus.COMPLETED:
            _notify_workflow(
                NotificationEvent.WORKFLOW_COMPLETED,
                workflow,
                NotificationPriority.NORMAL,
                metadata={"total_tasks": len(tasks)},
            )
        else:
            _notify_workflow(
                NotificationEvent.WORKFLOW_FAILED,
                workflow,
                NotificationPriority.HIGH,
                error_message=workflow.error_message,
            )

        return {"status": workflow.status.value, "workflow_id": workflow_id}

    finally:
        db.close()


# --------------------------------------------------------------------------------------
# SCHEDULING / HOUSEKEEPING (unchanged)
# --------------------------------------------------------------------------------------

@celery_app.task
def execute_scheduled_workflow(workflow_id: int):
    """Kick‑off a scheduled workflow and compute next_run_at."""
    db = SessionLocal()
    try:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow or not workflow.is_scheduled:
            return {"status": "skipped", "workflow_id": workflow_id}

        workflow.run_count += 1
        workflow.last_run_at = datetime.utcnow()
        try:
            tz = pytz.timezone(workflow.timezone)
            cron = croniter(workflow.cron_expression, datetime.now(tz))
            workflow.next_run_at = cron.get_next(datetime)
        except Exception as e:
            print(f"Failed to compute next run: {e}")
        db.commit()

        _notify_workflow(
            NotificationEvent.WORKFLOW_SCHEDULED,
            workflow,
            NotificationPriority.LOW,
            metadata={
                "run_count": workflow.run_count,
                "next_run_at": workflow.next_run_at.isoformat()
                if workflow.next_run_at
                else None,
            },
        )
        execute_workflow.delay(workflow_id)
        return {"status": "started", "workflow_id": workflow_id}
    finally:
        db.close()


@celery_app.task
def check_and_execute_scheduled_workflows():
    """Find due workflows and queue them."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        recent_cutoff = now - timedelta(minutes=5)

        due = (
            db.query(Workflow)
            .filter(
                Workflow.is_scheduled.is_(True),
                Workflow.next_run_at <= now,
                Workflow.status.in_(
                    [WorkflowStatus.PENDING, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]
                ),
            )
            .all()
        )
        executed = 0
        for wf in due:
            if wf.status == WorkflowStatus.RUNNING:
                continue
            execute_scheduled_workflow.delay(wf.id)
            executed += 1
        return {"status": "completed", "executed": executed}
    finally:
        db.close()


@celery_app.task
def cleanup_old_tasks():
    """Purge historical data to keep the DB small."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=settings.CLEANUP_DAYS)
        old_tasks = (
            db.query(Task)
            .filter(
                Task.completed_at < cutoff,
                Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED]),
            )
            .all()
        )
        for t in old_tasks:
            db.delete(t)
        old_wfs = (
            db.query(Workflow)
            .filter(
                Workflow.completed_at < cutoff,
                Workflow.status.in_([WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]),
            )
            .all()
        )
        for wf in old_wfs:
            db.delete(wf)
        db.commit()
        return f"Cleaned {len(old_tasks)} tasks, {len(old_wfs)} workflows"
    finally:
        db.close()


# --------------------------------------------------------------------------------------
# HELPER UTILITIES
# --------------------------------------------------------------------------------------

def _notify_workflow(event: NotificationEvent, workflow: Workflow, priority: NotificationPriority, **extra):
    try:
        trigger_notification(
            event=event,
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            priority=priority,
            **extra,
        )
    except Exception as e:
        print(f"Notification error ({event}): {e}")


def _notify_task(event: NotificationEvent, task: Task, workflow_name: str, priority: NotificationPriority, **extra):
    try:
        trigger_notification(
            event=event,
            workflow_id=task.workflow_id,
            workflow_name=workflow_name,
            task_id=task.id,
            task_name=task.name,
            priority=priority,
            **extra,
        )
    except Exception as e:
        print(f"Notification error ({event}): {e}")


def _fail_immediately(db: Session, task_id: int, message: str):
    """Utility to mark a task FAILED when we cannot proceed."""
    task: Task | None = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.status = TaskStatus.FAILED
        task.error_message = message
        task.completed_at = datetime.utcnow()
        db.commit()
        workflow = db.query(Workflow).filter(Workflow.id == task.workflow_id).first()
        workflow_name = workflow.name if workflow else f"Workflow {task.workflow_id}"
        _notify_task(
            NotificationEvent.TASK_FAILED,
            task,
            workflow_name,
            NotificationPriority.HIGH,
            error_message=message,
        )
    return {"status": "failed", "task_id": task_id, "error_message": message}
