# Notification System Documentation

## Overview

The Task Execution Engine now includes a comprehensive notification system that can send notifications via:
- **Email** (SMTP, Gmail, SendGrid)
- **SMS** (via Twilio)
- **Telegram** (via Telegram Bot API)
- **Desktop** (cross-platform desktop notifications)

Notifications are automatically sent when tasks and workflows start, complete, or fail.

## Quick Setup

1. **Install dependencies** (already added to requirements.txt):
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure notifications**:
   ```bash
   cp .env.notifications.example .env
   # Edit .env with your notification settings
   ```

3. **Restart the application** to load new environment variables.

## Supported Events

- `task_started` - When a task begins execution
- `task_completed` - When a task completes successfully  
- `task_failed` - When a task fails
- `workflow_started` - When a workflow begins
- `workflow_completed` - When a workflow completes successfully
- `workflow_failed` - When a workflow fails
- `workflow_scheduled` - When a scheduled workflow runs

## Priority Levels

- `low` - For informational notifications
- `normal` - For standard notifications
- `high` - For important events (failures)
- `urgent` - For critical events (bypasses quiet hours)

## API Endpoints

- `GET /api/v1/notifications/status` - Check notification provider status
- `POST /api/v1/notifications/test` - Send test notification
- `GET /api/v1/notifications/events` - List available events and priorities

## Features

- **Async Processing**: Notifications are sent asynchronously via Celery
- **Retry Logic**: Failed notifications are retried with exponential backoff
- **Quiet Hours**: Support for quiet hours with priority overrides
- **Multiple Providers**: Can use multiple notification methods simultaneously
- **Rich Content**: Includes workflow/task context and metadata
- **Graceful Degradation**: System continues working even if notifications fail

## Provider-Specific Setup

### Email (Gmail)
1. Enable 2-Factor Authentication
2. Generate App Password: Google Account → Security → App Passwords
3. Use app password in SMTP_PASSWORD

### SMS (Twilio)
1. Sign up at twilio.com
2. Get Account SID and Auth Token from Console
3. Purchase/verify phone numbers

### Telegram
1. Message @BotFather on Telegram
2. Create new bot: `/newbot`
3. Get bot token
4. Get chat ID by messaging bot, then visit:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`

## Environment Variables

See `.env.notifications.example` for complete configuration options.

## Testing

Test your notification setup:
```bash
curl -X POST "http://localhost:8000/api/v1/notifications/test" \
  -H "Content-Type: application/json" \
  -d '{"notification_type": "email", "recipient": "test@example.com"}'
```

## Troubleshooting

- Check logs for notification errors
- Verify provider credentials
- Test individual providers using the API
- Ensure firewall allows outbound connections
- For Gmail: check "Less secure app access" if needed

## Customization

The notification system is modular and extensible. You can:
- Add new notification providers in `app/notifications/providers.py`
- Customize message templates in `notification_service.py`
- Add database-backed configuration storage
- Implement user-specific notification preferences