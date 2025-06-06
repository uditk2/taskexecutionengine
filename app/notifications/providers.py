import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    import yagmail
    YAGMAIL_AVAILABLE = True
except ImportError:
    YAGMAIL_AVAILABLE = False

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

try:
    from plyer import notification as desktop_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

from .models import NotificationMessage, NotificationResult


logger = logging.getLogger(__name__)


class NotificationProvider(ABC):
    """Base class for notification providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> bool:
        """Validate provider configuration"""
        pass
    
    @abstractmethod
    async def send_notification(self, message: NotificationMessage) -> NotificationResult:
        """Send notification"""
        pass


class EmailProvider(NotificationProvider):
    """Email notification provider supporting multiple backends"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.backend = config.get('backend', 'smtp')  # smtp, yagmail, sendgrid
        
    def _validate_config(self) -> bool:
        """Validate email configuration"""
        if self.backend == 'yagmail':
            return YAGMAIL_AVAILABLE and all([
                self.config.get('username'),
                self.config.get('password')
            ])
        elif self.backend == 'sendgrid':
            return SENDGRID_AVAILABLE and self.config.get('api_key')
        else:  # smtp
            return all([
                self.config.get('smtp_server'),
                self.config.get('smtp_port'),
                self.config.get('username'),
                self.config.get('password')
            ])
    
    async def send_notification(self, message: NotificationMessage) -> NotificationResult:
        """Send email notification"""
        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="email",
                error="Email provider not properly configured"
            )
        
        try:
            if self.backend == 'yagmail':
                return await self._send_with_yagmail(message)
            elif self.backend == 'sendgrid':
                return await self._send_with_sendgrid(message)
            else:
                return await self._send_with_smtp(message)
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return NotificationResult(
                success=False,
                provider="email",
                error=str(e)
            )
    
    async def _send_with_yagmail(self, message: NotificationMessage) -> NotificationResult:
        """Send email using yagmail"""
        yag = yagmail.SMTP(
            self.config['username'],
            self.config['password']
        )
        
        yag.send(
            to=message.recipient_email,
            subject=message.title,
            contents=message.message
        )
        
        return NotificationResult(
            success=True,
            provider="email-yagmail",
            message="Email sent successfully"
        )
    
    async def _send_with_sendgrid(self, message: NotificationMessage) -> NotificationResult:
        """Send email using SendGrid"""
        mail = Mail(
            from_email=self.config.get('from_email', 'noreply@taskengine.com'),
            to_emails=message.recipient_email,
            subject=message.title,
            html_content=message.message
        )
        
        sg = SendGridAPIClient(api_key=self.config['api_key'])
        response = sg.send(mail)
        
        return NotificationResult(
            success=True,
            provider="email-sendgrid",
            message="Email sent successfully",
            message_id=response.headers.get('X-Message-Id')
        )
    
    async def _send_with_smtp(self, message: NotificationMessage) -> NotificationResult:
        """Send email using standard SMTP"""
        msg = MIMEMultipart()
        msg['From'] = self.config.get('from_email', self.config['username'])
        msg['To'] = message.recipient_email
        msg['Subject'] = message.title
        
        msg.attach(MIMEText(message.message, 'html'))
        
        server = smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port'])
        if self.config.get('use_tls', True):
            server.starttls()
        server.login(self.config['username'], self.config['password'])
        server.send_message(msg)
        server.quit()
        
        return NotificationResult(
            success=True,
            provider="email-smtp",
            message="Email sent successfully"
        )


class SMSProvider(NotificationProvider):
    """SMS notification provider using Twilio"""
    
    def _validate_config(self) -> bool:
        """Validate SMS configuration"""
        return TWILIO_AVAILABLE and all([
            self.config.get('account_sid'),
            self.config.get('auth_token'),
            self.config.get('from_number')
        ])
    
    async def send_notification(self, message: NotificationMessage) -> NotificationResult:
        """Send SMS notification"""
        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="sms",
                error="SMS provider not properly configured"
            )
        
        try:
            client = TwilioClient(
                self.config['account_sid'],
                self.config['auth_token']
            )
            
            sms_message = client.messages.create(
                body=f"{message.title}\n\n{message.message}",
                from_=self.config['from_number'],
                to=message.recipient_phone
            )
            
            return NotificationResult(
                success=True,
                provider="sms-twilio",
                message="SMS sent successfully",
                message_id=sms_message.sid
            )
        except Exception as e:
            logger.error(f"Failed to send SMS notification: {e}")
            return NotificationResult(
                success=False,
                provider="sms",
                error=str(e)
            )


class TelegramProvider(NotificationProvider):
    """Telegram notification provider"""
    
    def _validate_config(self) -> bool:
        """Validate Telegram configuration"""
        return TELEGRAM_AVAILABLE and self.config.get('bot_token')
    
    async def send_notification(self, message: NotificationMessage) -> NotificationResult:
        """Send Telegram notification"""
        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="telegram",
                error="Telegram provider not properly configured"
            )
        
        try:
            bot = Bot(token=self.config['bot_token'])
            
            telegram_message = f"*{message.title}*\n\n{message.message}"
            
            sent_message = await bot.send_message(
                chat_id=message.recipient_telegram_id,
                text=telegram_message,
                parse_mode='Markdown'
            )
            
            return NotificationResult(
                success=True,
                provider="telegram",
                message="Telegram message sent successfully",
                message_id=str(sent_message.message_id)
            )
        except TelegramError as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return NotificationResult(
                success=False,
                provider="telegram",
                error=str(e)
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return NotificationResult(
                success=False,
                provider="telegram",
                error=str(e)
            )


class DesktopProvider(NotificationProvider):
    """Desktop notification provider using plyer"""
    
    def _validate_config(self) -> bool:
        """Validate desktop notification configuration"""
        # Check if we're running in Docker
        if self._is_running_in_docker():
            logger.info("Desktop notifications disabled: running in Docker container")
            return False
            
        return PLYER_AVAILABLE
    
    def _is_running_in_docker(self) -> bool:
        """Check if we're running inside a Docker container"""
        try:
            # Check for Docker-specific files
            if os.path.exists('/.dockerenv'):
                return True
                
            # Check cgroup for docker
            with open('/proc/1/cgroup', 'r') as f:
                content = f.read()
                if 'docker' in content or 'containerd' in content:
                    return True
        except (FileNotFoundError, PermissionError):
            pass
            
        # Check for common Docker environment variables
        docker_env_vars = ['DOCKER_CONTAINER', 'CONTAINER_NAME']
        for env_var in docker_env_vars:
            if os.getenv(env_var):
                return True
                
        return False
    
    async def send_notification(self, message: NotificationMessage) -> NotificationResult:
        """Send desktop notification"""
        if not self.enabled:
            return NotificationResult(
                success=False,
                provider="desktop",
                error="Desktop notifications not available (disabled in Docker environment)"
            )
        
        try:
            desktop_notification.notify(
                title=message.title,
                message=message.message,
                timeout=self.config.get('timeout', 10),
                app_name=self.config.get('app_name', 'Task Engine'),
                app_icon=self.config.get('app_icon')
            )
            
            return NotificationResult(
                success=True,
                provider="desktop",
                message="Desktop notification sent successfully"
            )
        except Exception as e:
            logger.error(f"Failed to send desktop notification: {e}")
            return NotificationResult(
                success=False,
                provider="desktop",
                error=str(e)
            )