from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.notifications.notification_service import NotificationService
from app.notifications.models import (
    NotificationConfig, 
    NotificationEvent, 
    NotificationPriority,
    NotificationType
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

# Request/Response models
class NotificationConfigRequest(BaseModel):
    workflow_id: Optional[int] = None
    task_id: Optional[int] = None
    email_enabled: bool = False
    sms_enabled: bool = False
    telegram_enabled: bool = False
    desktop_enabled: bool = False
    email_address: Optional[str] = None
    phone_number: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    events: List[NotificationEvent] = []
    priority_filter: NotificationPriority = NotificationPriority.NORMAL
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: str = "UTC"

class NotificationTestRequest(BaseModel):
    notification_type: NotificationType
    recipient: str
    message: str = "Test notification from Task Engine"

class NotificationStatusResponse(BaseModel):
    providers: dict
    default_config: Optional[NotificationConfig]

@router.get("/status")
async def get_notification_status():
    """Get status of notification providers and default configuration"""
    service = NotificationService()
    
    # Get provider status
    provider_status = service.get_provider_status()
    
    # Get default config if available
    default_configs = await service._get_notification_configs(workflow_id=0)
    default_config = default_configs[0] if default_configs else None
    
    return NotificationStatusResponse(
        providers=provider_status,
        default_config=default_config
    )

@router.post("/test")
async def test_notification(request: NotificationTestRequest):
    """Send a test notification"""
    from app.notifications.models import NotificationMessage
    from app.notifications.tasks import trigger_notification
    
    try:
        # Create test notification
        result = trigger_notification(
            event=NotificationEvent.TASK_COMPLETED,
            workflow_id=0,
            workflow_name="Test Workflow",
            task_id=0,
            task_name="Test Task",
            priority=NotificationPriority.NORMAL,
            async_send=False  # Send synchronously for immediate feedback
        )
        
        return {
            "success": True,
            "message": "Test notification sent",
            "results": [r.dict() for r in result] if result else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send test notification: {str(e)}")

@router.get("/events")
async def get_notification_events():
    """Get available notification events"""
    return {
        "events": [event.value for event in NotificationEvent],
        "priorities": [priority.value for priority in NotificationPriority],
        "types": [ntype.value for ntype in NotificationType]
    }

# Include the router in the main routes
def include_notification_routes(app):
    app.include_router(router)