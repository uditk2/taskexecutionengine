from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "task_execution_engine",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.workflow_tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.TASK_TIMEOUT,
    task_soft_time_limit=settings.TASK_TIMEOUT - 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-old-tasks': {
        'task': 'app.tasks.workflow_tasks.cleanup_old_tasks',
        'schedule': 3600.0  # Run every hour
    },
    'check-scheduled-workflows': {
        'task': 'app.tasks.workflow_tasks.check_and_execute_scheduled_workflows',
        'schedule': 60.0  # Check every minute
    }
}