import os
import logging
import asyncio
from datetime import datetime, time
from typing import Dict, List, Optional, Any
import pytz

from .models import (
    NotificationConfig, 
    NotificationMessage, 
    NotificationResult, 
    NotificationEvent,
    NotificationType,
    NotificationPriority
)
from .providers import (
    EmailProvider, 
    SMSProvider, 
    TelegramProvider, 
    DesktopProvider
)


logger = logging.getLogger(__name__)


class NotificationService:
    """Main notification service that handles all notification types"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._load_config_from_env()
        self.providers = self._initialize_providers()
        
    def _load_config_from_env(self) -> Dict[str, Any]:
        """Load notification configuration from environment variables"""
        return {
            'email': {
                'backend': os.getenv('EMAIL_BACKEND', 'smtp'),
                'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
                'smtp_port': int(os.getenv('SMTP_PORT', '587')),
                'username': os.getenv('SMTP_USERNAME'),
                'password': os.getenv('SMTP_PASSWORD'),
                'from_email': os.getenv('FROM_EMAIL'),
                'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
                # SendGrid
                'api_key': os.getenv('SENDGRID_API_KEY'),
            },
            'sms': {
                'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
                'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
                'from_number': os.getenv('TWILIO_FROM_NUMBER'),
            },
            'telegram': {
                'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            },
            'desktop': {
                'timeout': int(os.getenv('DESKTOP_NOTIFICATION_TIMEOUT', '10')),
                'app_name': os.getenv('DESKTOP_APP_NAME', 'Task Engine'),
                'app_icon': os.getenv('DESKTOP_APP_ICON'),
            }
        }
    
    def _initialize_providers(self) -> Dict[str, Any]:
        """Initialize notification providers"""
        providers = {}
        
        try:
            providers['email'] = EmailProvider(self.config.get('email', {}))
        except Exception as e:
            logger.warning(f"Failed to initialize email provider: {e}")
            
        try:
            providers['sms'] = SMSProvider(self.config.get('sms', {}))
        except Exception as e:
            logger.warning(f"Failed to initialize SMS provider: {e}")
            
        try:
            providers['telegram'] = TelegramProvider(self.config.get('telegram', {}))
        except Exception as e:
            logger.warning(f"Failed to initialize Telegram provider: {e}")
            
        try:
            providers['desktop'] = DesktopProvider(self.config.get('desktop', {}))
        except Exception as e:
            logger.warning(f"Failed to initialize desktop provider: {e}")
        
        return providers
    
    async def send_notification(
        self, 
        message: NotificationMessage, 
        notification_config: NotificationConfig
    ) -> List[NotificationResult]:
        """Send notification using configured providers"""
        results = []
        
        # Check if we should send notifications during quiet hours
        if not self._should_send_during_quiet_hours(notification_config, message):
            logger.info(f"Skipping notification during quiet hours: {message.title}")
            return [NotificationResult(
                success=False,
                provider="all",
                message="Notification skipped due to quiet hours"
            )]
        
        # Check priority filter
        if not self._meets_priority_threshold(notification_config, message):
            logger.info(f"Skipping notification due to priority filter: {message.title}")
            return [NotificationResult(
                success=False,
                provider="all",
                message="Notification skipped due to priority filter"
            )]
        
        # Check event filter
        if not self._is_event_enabled(notification_config, message):
            logger.info(f"Skipping notification for disabled event: {message.event}")
            return [NotificationResult(
                success=False,
                provider="all",
                message="Notification skipped due to event filter"
            )]
        
        # Send notifications
        tasks = []
        
        if notification_config.email_enabled and message.recipient_email:
            if 'email' in self.providers:
                tasks.append(self.providers['email'].send_notification(message))
        
        if notification_config.sms_enabled and message.recipient_phone:
            if 'sms' in self.providers:
                tasks.append(self.providers['sms'].send_notification(message))
        
        if notification_config.telegram_enabled and message.recipient_telegram_id:
            if 'telegram' in self.providers:
                tasks.append(self.providers['telegram'].send_notification(message))
        
        if notification_config.desktop_enabled:
            if 'desktop' in self.providers:
                tasks.append(self.providers['desktop'].send_notification(message))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Convert exceptions to error results
            processed_results = []
            for result in results:
                if isinstance(result, Exception):
                    processed_results.append(NotificationResult(
                        success=False,
                        provider="unknown",
                        error=str(result)
                    ))
                else:
                    processed_results.append(result)
            results = processed_results
        
        return results
    
    def _should_send_during_quiet_hours(
        self, 
        config: NotificationConfig, 
        message: NotificationMessage
    ) -> bool:
        """Check if notification should be sent during quiet hours"""
        if not config.quiet_hours_start or not config.quiet_hours_end:
            return True
        
        # High priority and urgent messages bypass quiet hours
        if message.priority in [NotificationPriority.HIGH, NotificationPriority.URGENT]:
            return True
        
        try:
            tz = pytz.timezone(config.timezone)
            current_time = datetime.now(tz).time()
            
            quiet_start = time.fromisoformat(config.quiet_hours_start)
            quiet_end = time.fromisoformat(config.quiet_hours_end)
            
            # Handle overnight quiet hours (e.g., 22:00 to 08:00)
            if quiet_start > quiet_end:
                return not (current_time >= quiet_start or current_time <= quiet_end)
            else:
                return not (quiet_start <= current_time <= quiet_end)
        except Exception as e:
            logger.warning(f"Error checking quiet hours: {e}")
            return True
    
    def _meets_priority_threshold(
        self, 
        config: NotificationConfig, 
        message: NotificationMessage
    ) -> bool:
        """Check if message priority meets the configured threshold"""
        priority_levels = {
            NotificationPriority.LOW: 0,
            NotificationPriority.NORMAL: 1,
            NotificationPriority.HIGH: 2,
            NotificationPriority.URGENT: 3
        }
        
        return priority_levels.get(message.priority, 1) >= priority_levels.get(config.priority_filter, 1)
    
    def _is_event_enabled(
        self, 
        config: NotificationConfig, 
        message: NotificationMessage
    ) -> bool:
        """Check if the event type is enabled for notifications"""
        if not config.events:
            return True  # If no specific events configured, allow all
        
        return message.event in config.events
    
    async def send_task_notification(
        self,
        event: NotificationEvent,
        task_id: int,
        task_name: str,
        workflow_id: int,
        workflow_name: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[NotificationResult]:
        """Convenience method to send task-related notifications"""
        
        # Generate message content based on event
        title, message = self._generate_task_message(
            event, task_name, workflow_name, error_message
        )
        
        notification_message = NotificationMessage(
            event=event,
            title=title,
            message=message,
            priority=priority,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            task_id=task_id,
            task_name=task_name,
            metadata=metadata or {}
        )
        
        # Get notification configs for this workflow/task
        configs = await self._get_notification_configs(workflow_id, task_id)
        
        all_results = []
        for config in configs:
            # Set recipient details
            notification_message.recipient_email = config.email_address
            notification_message.recipient_phone = config.phone_number
            notification_message.recipient_telegram_id = config.telegram_chat_id
            
            results = await self.send_notification(notification_message, config)
            all_results.extend(results)
        
        return all_results
    
    async def send_workflow_notification(
        self,
        event: NotificationEvent,
        workflow_id: int,
        workflow_name: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[NotificationResult]:
        """Convenience method to send workflow-related notifications"""
        
        # Generate message content based on event
        title, message = self._generate_workflow_message(
            event, workflow_name, error_message
        )
        
        notification_message = NotificationMessage(
            event=event,
            title=title,
            message=message,
            priority=priority,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            metadata=metadata or {}
        )
        
        # Get notification configs for this workflow
        configs = await self._get_notification_configs(workflow_id)
        
        all_results = []
        for config in configs:
            # Set recipient details
            notification_message.recipient_email = config.email_address
            notification_message.recipient_phone = config.phone_number
            notification_message.recipient_telegram_id = config.telegram_chat_id
            
            results = await self.send_notification(notification_message, config)
            all_results.extend(results)
        
        return all_results
    
    def _generate_task_message(
        self, 
        event: NotificationEvent, 
        task_name: str, 
        workflow_name: str,
        error_message: Optional[str] = None
    ) -> tuple[str, str]:
        """Generate notification title and message for task events"""
        
        if event == NotificationEvent.TASK_STARTED:
            title = f"Task Started: {task_name}"
            message = f"Task '{task_name}' in workflow '{workflow_name}' has started execution."
        elif event == NotificationEvent.TASK_COMPLETED:
            title = f"Task Completed: {task_name}"
            message = f"Task '{task_name}' in workflow '{workflow_name}' has completed successfully."
        elif event == NotificationEvent.TASK_FAILED:
            title = f"Task Failed: {task_name}"
            message = f"Task '{task_name}' in workflow '{workflow_name}' has failed."
            if error_message:
                message += f"\n\nError: {error_message}"
        else:
            title = f"Task Update: {task_name}"
            message = f"Task '{task_name}' in workflow '{workflow_name}' - {event.value}"
        
        return title, message
    
    def _generate_workflow_message(
        self, 
        event: NotificationEvent, 
        workflow_name: str,
        error_message: Optional[str] = None
    ) -> tuple[str, str]:
        """Generate notification title and message for workflow events"""
        
        if event == NotificationEvent.WORKFLOW_STARTED:
            title = f"Workflow Started: {workflow_name}"
            message = f"Workflow '{workflow_name}' has started execution."
        elif event == NotificationEvent.WORKFLOW_COMPLETED:
            title = f"Workflow Completed: {workflow_name}"
            message = f"Workflow '{workflow_name}' has completed successfully."
        elif event == NotificationEvent.WORKFLOW_FAILED:
            title = f"Workflow Failed: {workflow_name}"
            message = f"Workflow '{workflow_name}' has failed."
            if error_message:
                message += f"\n\nError: {error_message}"
        elif event == NotificationEvent.WORKFLOW_SCHEDULED:
            title = f"Workflow Scheduled: {workflow_name}"
            message = f"Workflow '{workflow_name}' has been scheduled for execution."
        else:
            title = f"Workflow Update: {workflow_name}"
            message = f"Workflow '{workflow_name}' - {event.value}"
        
        return title, message
    
    async def _get_notification_configs(
        self, 
        workflow_id: int, 
        task_id: Optional[int] = None
    ) -> List[NotificationConfig]:
        """Get notification configurations for workflow/task from database"""
        from app.core.database import SessionLocal
        from sqlalchemy import text
        
        configs = []
        db = SessionLocal()
        
        try:
            # Query notification configs from database
            query = """
                SELECT * FROM notification_configs 
                WHERE (workflow_id = :workflow_id OR workflow_id IS NULL)
                AND (task_id = :task_id OR task_id IS NULL)
                ORDER BY 
                    CASE WHEN workflow_id = :workflow_id AND task_id = :task_id THEN 1
                         WHEN workflow_id = :workflow_id AND task_id IS NULL THEN 2
                         WHEN workflow_id IS NULL AND task_id IS NULL THEN 3
                         ELSE 4 END
            """
            
            result = db.execute(text(query), {
                "workflow_id": workflow_id,
                "task_id": task_id
            })
            
            for row in result:
                # Parse events JSON
                events = []
                if row.events:
                    import json
                    try:
                        event_list = json.loads(row.events) if isinstance(row.events, str) else row.events
                        events = [NotificationEvent(event) for event in event_list]
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Invalid events JSON in config {row.id}: {e}")
                
                config = NotificationConfig(
                    id=row.id,
                    user_id=row.user_id,
                    workflow_id=row.workflow_id,
                    task_id=row.task_id,
                    email_enabled=row.email_enabled,
                    sms_enabled=row.sms_enabled,
                    telegram_enabled=row.telegram_enabled,
                    desktop_enabled=row.desktop_enabled,
                    email_address=row.email_address,
                    phone_number=row.phone_number,
                    telegram_chat_id=row.telegram_chat_id,
                    events=events,
                    priority_filter=NotificationPriority(row.priority_filter),
                    quiet_hours_start=row.quiet_hours_start.strftime('%H:%M') if row.quiet_hours_start else None,
                    quiet_hours_end=row.quiet_hours_end.strftime('%H:%M') if row.quiet_hours_end else None,
                    timezone=row.timezone,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                )
                configs.append(config)
        
        except Exception as e:
            logger.warning(f"Failed to load notification configs from database: {e}")
            # Fall back to environment-based config
            configs = self._get_env_based_configs(workflow_id, task_id)
        finally:
            db.close()
        
        # If no configs found, try environment variables as fallback
        if not configs:
            configs = self._get_env_based_configs(workflow_id, task_id)
        
        return configs
    
    def _get_env_based_configs(
        self, 
        workflow_id: int, 
        task_id: Optional[int] = None
    ) -> List[NotificationConfig]:
        """Get notification configurations from environment variables (fallback)"""
        configs = []
        
        # Check if we have default notification settings in environment
        default_email = os.getenv('DEFAULT_NOTIFICATION_EMAIL')
        default_phone = os.getenv('DEFAULT_NOTIFICATION_PHONE')
        default_telegram = os.getenv('DEFAULT_NOTIFICATION_TELEGRAM_CHAT_ID')
        
        if any([default_email, default_phone, default_telegram]):
            config = NotificationConfig(
                workflow_id=workflow_id,
                task_id=task_id,
                email_enabled=bool(default_email),
                sms_enabled=bool(default_phone),
                telegram_enabled=bool(default_telegram),
                desktop_enabled=True,
                email_address=default_email,
                phone_number=default_phone,
                telegram_chat_id=default_telegram,
                events=[
                    NotificationEvent.TASK_COMPLETED,
                    NotificationEvent.TASK_FAILED,
                    NotificationEvent.WORKFLOW_COMPLETED,
                    NotificationEvent.WORKFLOW_FAILED
                ],
                priority_filter=NotificationPriority.NORMAL
            )
            configs.append(config)
        
        return configs
    
    async def log_notification_result(
        self,
        workflow_id: int,
        task_id: Optional[int],
        event: NotificationEvent,
        result: NotificationResult,
        message: NotificationMessage
    ):
        """Log notification result to database"""
        from app.core.database import SessionLocal
        from sqlalchemy import text
        
        db = SessionLocal()
        try:
            # Insert into notification_history table
            insert_query = """
                INSERT INTO notification_history (
                    workflow_id, task_id, event, provider, recipient, title, message,
                    priority, success, error_message, provider_message_id, metadata, sent_at
                ) VALUES (
                    :workflow_id, :task_id, :event, :provider, :recipient, :title, :message,
                    :priority, :success, :error_message, :provider_message_id, :metadata, :sent_at
                )
            """
            
            # Determine recipient based on provider
            recipient = "unknown"
            if "email" in result.provider and message.recipient_email:
                recipient = message.recipient_email
            elif "sms" in result.provider and message.recipient_phone:
                recipient = message.recipient_phone
            elif "telegram" in result.provider and message.recipient_telegram_id:
                recipient = message.recipient_telegram_id
            elif "desktop" in result.provider:
                recipient = "desktop"
            
            import json
            
            db.execute(text(insert_query), {
                "workflow_id": workflow_id,
                "task_id": task_id,
                "event": event.value,
                "provider": result.provider,
                "recipient": recipient,
                "title": message.title,
                "message": message.message,
                "priority": message.priority.value,
                "success": result.success,
                "error_message": result.error,
                "provider_message_id": result.message_id,
                "metadata": json.dumps(message.metadata),
                "sent_at": result.sent_at
            })
            db.commit()
            
        except Exception as e:
            logger.warning(f"Failed to log notification result: {e}")
            db.rollback()
        finally:
            db.close()