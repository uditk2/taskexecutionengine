from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db, check_db_health
from app.api.routes import base, example, workflows, dashboard, notifications
from app.middleware import logging_middleware, auth_middleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Task Execution Engine...")
    try:
        # Import executors to register them
        from app.executors import venv_executor, docker_executor
        logger.info("Task executors registered")

        # Initialize database
        init_db()
        logger.info("Database initialized successfully")

        # Check database health
        if check_db_health():
            logger.info("Database health check passed")
        else:
            logger.error("Database health check failed")
            raise Exception("Database is not healthy")

        logger.info("Task Execution Engine started successfully")
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Task Execution Engine...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
    debug=settings.DEBUG
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Configure templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Add middleware
app.add_middleware(logging_middleware.LoggingMiddleware)
app.add_middleware(auth_middleware.AuthMiddleware)

# Include routers
app.include_router(base.router)
app.include_router(example.router, prefix="/example")
app.include_router(workflows.router, prefix=settings.API_PREFIX)
app.include_router(dashboard.router)
app.include_router(notifications.router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_healthy = check_db_health()
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "version": settings.PROJECT_VERSION
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
