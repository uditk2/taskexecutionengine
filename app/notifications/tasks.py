import asyncio
import logging
from celery import shared_task
from typing import Dict, Any, Optional, List

from app.celery_app import celery_app
from app.notifications.notification_service import NotificationService
from app.notifications.models import NotificationEvent, NotificationPriority

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def send_notification_task(
    self,
    event: str,
    workflow_id: int,
    workflow_name: str,
    task_id: Optional[int] = None,
    task_name: Optional[str] = None,
    priority: str = "normal",
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Celery task to send notifications asynchronously"""
    try:
        # Initialize notification service
        notification_service = NotificationService()
        
        # Convert string enums back to enum types
        event_enum = NotificationEvent(event)
        priority_enum = NotificationPriority(priority)
        
        # Send notification based on type
        if task_id and task_name:
            # Task notification
            results = asyncio.run(
                notification_service.send_task_notification(
                    event=event_enum,
                    task_id=task_id,
                    task_name=task_name,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    priority=priority_enum,
                    error_message=error_message,
                    metadata=metadata
                )
            )
        else:
            # Workflow notification
            results = asyncio.run(
                notification_service.send_workflow_notification(
                    event=event_enum,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    priority=priority_enum,
                    error_message=error_message,
                    metadata=metadata
                )
            )
        
        # Log all results to database
        for result in results:
            try:
                # Create a basic message for logging
                title, message = notification_service._generate_workflow_message(event_enum, workflow_name, error_message) if not task_name else notification_service._generate_task_message(event_enum, task_name, workflow_name, error_message)
                
                from app.notifications.models import NotificationMessage
                log_message = NotificationMessage(
                    event=event_enum,
                    title=title,
                    message=message,
                    priority=priority_enum,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    task_id=task_id,
                    task_name=task_name,
                    metadata=metadata or {}
                )
                
                asyncio.run(notification_service.log_notification_result(
                    workflow_id=workflow_id,
                    task_id=task_id,
                    event=event_enum,
                    result=result,
                    message=log_message
                ))
            except Exception as log_error:
                logger.warning(f"Failed to log notification result: {log_error}")
        
        successful_notifications = [r for r in results if r.success]
        failed_notifications = [r for r in results if not r.success]
        
        logger.info(f"Sent {len(successful_notifications)} notifications successfully, {len(failed_notifications)} failed")
        
        return {
            "success": True,
            "sent": len(successful_notifications),
            "failed": len(failed_notifications),
            "results": [r.dict() for r in results]
        }
        
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        # Log the failure to database if possible
        try:
            service = NotificationService()
            from app.notifications.models import NotificationResult, NotificationMessage
            
            failed_result = NotificationResult(
                success=False,
                provider="celery_task",
                error=str(e)
            )
            
            title = f"Notification Task Failed"
            message = f"Failed to send {event} notification for workflow '{workflow_name}'"
            if task_name:
                message += f" task '{task_name}'"
            
            log_message = NotificationMessage(
                event=NotificationEvent(event),
                title=title,
                message=message,
                priority=NotificationPriority(priority),
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                task_id=task_id,
                task_name=task_name,
                metadata=metadata or {}
            )
            
            asyncio.run(service.log_notification_result(
                workflow_id=workflow_id,
                task_id=task_id,
                event=NotificationEvent(event),
                result=failed_result,
                message=log_message
            ))
        except Exception as log_error:
            logger.warning(f"Failed to log notification failure: {log_error}")
        
        raise


def trigger_notification(
    event: NotificationEvent,
    workflow_id: int,
    workflow_name: str,
    task_id: Optional[int] = None,
    task_name: Optional[str] = None,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    async_send: bool = True
) -> Optional[Any]:
    """
    Convenience function to trigger notifications
    
    Args:
        event: The notification event type
        workflow_id: ID of the workflow
        workflow_name: Name of the workflow
        task_id: ID of the task (for task events)
        task_name: Name of the task (for task events)
        priority: Priority level of the notification
        error_message: Error message if applicable
        metadata: Additional metadata
        async_send: Whether to send asynchronously via Celery
    
    Returns:
        Celery task result if async_send=True, otherwise notification results
    """
    if async_send:
        # Send asynchronously via Celery
        return send_notification_task.delay(
            event=event.value,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            task_id=task_id,
            task_name=task_name,
            priority=priority.value,
            error_message=error_message,
            metadata=metadata
        )
    else:
        # Send synchronously
        notification_service = NotificationService()
        
        if task_id and task_name:
            return asyncio.run(
                notification_service.send_task_notification(
                    event=event,
                    task_id=task_id,
                    task_name=task_name,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    priority=priority,
                    error_message=error_message,
                    metadata=metadata
                )
            )
        else:
            return asyncio.run(
                notification_service.send_workflow_notification(
                    event=event,
                    workflow_id=workflow_id,
                    workflow_name=workflow_name,
                    priority=priority,
                    error_message=error_message,
                    metadata=metadata
                )
            )