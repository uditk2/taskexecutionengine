# Docker Deployment Guide with Notification System

## Quick Start

Deploy the complete Task Execution Engine with notification system in one command:

```bash
make deploy
```

This will:
1. Set up notification configuration files
2. Build all Docker images
3. Start all services with automatic database migrations
4. Display setup instructions

## Manual Deployment Steps

### 1. Configure Notifications

```bash
# Set up notification configuration
make setup-notifications

# Edit the .env file to configure your notification providers
nano .env
```

### 2. Build and Start Services

```bash
# Build Docker images
make build

# Start all services
make up
```

### 3. Verify Deployment

```bash
# Check service status
make status

# View logs to ensure migrations completed
make logs-migrations

# Test notification system
make check-notifications
```

## Container Architecture

The deployment includes these services:

- **web**: FastAPI application server (port 8000)
- **worker**: Celery workers for task execution and notifications
- **scheduler**: Celery beat for scheduled workflows
- **flower**: Celery monitoring UI (port 5555)
- **db**: PostgreSQL database (port 5432)
- **redis**: Redis for message brokering

## Database Migrations

Migrations run automatically during container startup via the `entrypoint.sh` script:

1. **Task Outputs Migration** - Adds task_outputs column
2. **Workflow Scheduling Migration** - Adds scheduling columns  
3. **Notification System Migration** - Creates notification tables

You can monitor migration progress with:
```bash
make logs-migrations
```

## Notification Configuration

### Email (Gmail Example)
```bash
# In .env file:
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com
```

### SMS (Twilio)
```bash
# In .env file:
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+1234567890
```

### Telegram
```bash
# In .env file:
TELEGRAM_BOT_TOKEN=your-bot-token
```

### Default Recipients
```bash
# In .env file:
DEFAULT_NOTIFICATION_EMAIL=admin@example.com
DEFAULT_NOTIFICATION_PHONE=+1234567890
DEFAULT_NOTIFICATION_TELEGRAM_CHAT_ID=123456789
```

## Testing Notifications

```bash
# Check notification system status
make check-notifications

# Send test notification
make test-notifications

# Or manually test via API:
curl -X POST "http://localhost:8000/api/v1/notifications/test" \
  -H "Content-Type: application/json" \
  -d '{"notification_type": "email", "recipient": "test@example.com"}'
```

## Useful Commands

```bash
# View logs
make logs              # All services
make logs-web          # Web service only
make logs-worker       # Worker service only

# Restart services
make restart           # All services
make restart-web       # Web service only
make restart-worker    # Worker service only

# Scale workers
make scale-workers WORKERS=4

# Access containers
make shell-web         # Web container shell
make shell-worker      # Worker container shell
make db-shell          # Database shell
make redis-shell       # Redis shell

# Cleanup
make down              # Stop services
make clean             # Remove containers and volumes
```

## Service URLs

After deployment, access these URLs:

- **Web UI**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Notification Status**: http://localhost:8000/api/v1/notifications/status
- **Flower (Celery UI)**: http://localhost:5555

## Troubleshooting

### Migration Issues
```bash
# Check migration logs
make logs-migrations

# If migrations fail, check database connectivity
make db-shell
```

### Notification Issues
```bash
# Check notification provider status
make check-notifications

# View worker logs for notification errors
make logs-worker

# Test individual providers
curl http://localhost:8000/api/v1/notifications/events
```

### Container Issues
```bash
# Check service status
make status

# View all logs
make logs

# Restart problematic services
make restart-web
make restart-worker
```

## Environment Variables

All notification environment variables are pre-configured in `docker-compose.yml`. Just uncomment and set the values you need in your `.env` file.

## Data Persistence

- **Database**: Stored in `postgres_data` volume
- **Task Environments**: Stored in `task_venvs` volume
- **Logs**: Mounted to `./logs` directory

Volumes persist data across container restarts.

## Production Considerations

1. **Secrets Management**: Use Docker secrets or external secret management
2. **SSL/TLS**: Add reverse proxy (nginx) with SSL certificates
3. **Monitoring**: Set up log aggregation and monitoring
4. **Backup**: Regular database backups
5. **Scaling**: Scale workers based on load
6. **Security**: Firewall configuration, network segmentation