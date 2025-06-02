# Task Execution Engine

A containerized, production-ready Python web service for executing and managing workflows using FastAPI, SQLAlchemy, and Celery.

## Features

- **Workflow Management**: Create, execute, monitor, cancel, and delete workflows
- **Task Execution**: Execute Python scripts in isolated virtual environments
- **Real-time Monitoring**: Web dashboard with auto-refresh capabilities
- **Scalable Architecture**: Containerized with Docker Compose
- **Persistent Storage**: PostgreSQL for workflow/task metadata
- **Message Queue**: Redis as Celery broker for task distribution
- **RESTful API**: Complete API for programmatic workflow management

## Architecture

- **Web Service**: FastAPI application serving REST API and web dashboard
- **Celery Worker**: Background task execution with virtual environment isolation
- **Celery Beat**: Periodic task scheduler for cleanup and maintenance
- **PostgreSQL**: Database for workflow and task metadata
- **Redis**: Message broker for Celery task queue
- **Flower**: Celery monitoring interface

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd TaskExecutionEngine
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your configuration if needed
```

3. Start all services:
```bash
docker-compose up -d
```

4. Verify services are running:
```bash
docker-compose ps
```

### Access Points

- **Web Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Flower (Celery Monitor)**: http://localhost:5555
- **Health Check**: http://localhost:8000/health

## API Usage

### Create and Execute Workflow

```bash
curl -X POST "http://localhost:8000/api/v1/workflows/?execute=true" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sample Workflow",
    "description": "A simple test workflow",
    "tasks": [
      {
        "name": "Hello World",
        "description": "Print hello world",
        "script_content": "print(\"Hello, World!\")",
        "requirements": [],
        "order": 0
      },
      {
        "name": "Math Calculation",
        "description": "Perform some calculations",
        "script_content": "import math\nresult = math.sqrt(16)\nprint(f\"Square root of 16 is: {result}\")",
        "requirements": [],
        "order": 1
      }
    ]
  }'
```

### List Workflows

```bash
curl -X GET "http://localhost:8000/api/v1/workflows/"
```

### Get Workflow Status

```bash
curl -X GET "http://localhost:8000/api/v1/workflows/{workflow_id}/status"
```

### Cancel Workflow

```bash
curl -X POST "http://localhost:8000/api/v1/workflows/{workflow_id}/cancel"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@postgres:5432/task_engine` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend URL | `redis://redis:6379/0` |
| `TASK_TIMEOUT` | Task execution timeout (seconds) | `3600` |
| `POLL_INTERVAL` | Dashboard refresh interval (seconds) | `15` |
| `VENV_BASE_PATH` | Base path for virtual environments | `/tmp/task_venvs` |

### Database Configuration

The application automatically creates database tables on startup. For production deployments, consider:

- Using managed PostgreSQL services
- Setting up database backups
- Configuring connection pooling

### Scaling

To scale workers horizontally:

```bash
docker-compose up -d --scale worker=4
```

## Development

### Local Development Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Start PostgreSQL and Redis:
```bash
docker-compose up -d postgres redis
```

3. Set environment variables:
```bash
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/task_engine"
export REDIS_URL="redis://localhost:6379/0"
```

4. Run the application:
```bash
uvicorn app.main:app --reload
```

5. Start Celery worker (in another terminal):
```bash
celery -A app.celery_app worker --loglevel=info
```

6. Start Celery beat (in another terminal):
```bash
celery -A app.celery_app beat --loglevel=info
```

### Running Tests

```bash
pytest
```

## Monitoring and Logging

### Logs

Application logs are stored in the `./logs` directory and mounted as volumes in containers.

### Flower Dashboard

Access Celery monitoring at http://localhost:5555 to view:
- Active workers
- Task statistics
- Queue status
- Task history

### Health Checks

The application includes health check endpoints:
- `/health` - Basic application health
- Docker health checks for all services

## Security Considerations

- Change default passwords in production
- Use environment-specific configuration
- Implement proper network security
- Consider adding authentication/authorization
- Regularly update dependencies

## Troubleshooting

### Common Issues

1. **Database Connection Issues**:
   - Verify PostgreSQL is running
   - Check connection string format
   - Ensure database exists

2. **Celery Worker Issues**:
   - Check Redis connectivity
   - Verify worker logs
   - Ensure proper permissions for virtual environment creation

3. **Task Execution Failures**:
   - Check task logs in database
   - Verify Python script syntax
   - Ensure required packages are available

### Logs and Debugging

```bash
# View application logs
docker-compose logs web

# View worker logs
docker-compose logs worker

# View all logs
docker-compose logs -f
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.
