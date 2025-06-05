from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from dataclasses import dataclass, field


class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    DESKTOP = "desktop"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationEvent(str, Enum):
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_SCHEDULED = "workflow_scheduled"


@dataclass
class NotificationConfig:
    """Configuration for notifications"""
    id: Optional[int] = None
    user_id: Optional[str] = None
    workflow_id: Optional[int] = None
    task_id: Optional[int] = None
    email_enabled: bool = False
    sms_enabled: bool = False
    telegram_enabled: bool = False
    desktop_enabled: bool = False
    email_address: Optional[str] = None
    phone_number: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    events: List[NotificationEvent] = field(default_factory=list)
    priority_filter: NotificationPriority = NotificationPriority.NORMAL
    quiet_hours_start: Optional[str] = None  # Format: "HH:MM"
    quiet_hours_end: Optional[str] = None    # Format: "HH:MM"
    timezone: str = "UTC"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotificationMessage(BaseModel):
    """Represents a notification message to be sent"""
    event: NotificationEvent
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    
    # Context data
    workflow_id: Optional[int] = None
    workflow_name: Optional[str] = None
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    
    # Recipient details
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    recipient_telegram_id: Optional[str] = None
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class NotificationResult:
    """Result of sending a notification"""
    success: bool
    provider: str
    message: Optional[str] = None
    error: Optional[str] = None
    message_id: Optional[str] = None
    sent_at: Optional[datetime] = field(default_factory=datetime.utcnow)
    
    def dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'success': self.success,
            'provider': self.provider,
            'message': self.message,
            'error': self.error,
            'message_id': self.message_id,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None
        }