import secrets
from typing import Any, Dict, List, Optional

from pydantic import validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Task Execution Engine"
    PROJECT_DESCRIPTION: str = "Containerized Python Task Execution Engine with Celery"
    PROJECT_VERSION: str = "1.0.0"
    
    API_PREFIX: str = "/api/v1"
    
    SECRET_KEY: str = secrets.token_urlsafe(32)
    
    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
    # Template settings
    DEFAULT_LAYOUT: str = "default"
    DEFAULT_NAVBAR: str = "top_fixed"
    
    # Database settings
    DATABASE_URL: str = "sqlite:///./task_engine.db"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "task_engine"
    POSTGRES_PORT: str = "5432"
    
    # Redis/Celery settings
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Task execution settings
    TASK_TIMEOUT: int = 3600  # 1 hour
    MAX_RETRIES: int = 3
    POLL_INTERVAL: int = 15  # seconds
    MIN_POLL_INTERVAL: int = 5  # seconds
    
    # Virtual environment settings
    VENV_BASE_PATH: str = "/tmp/task_venvs"
    
    # Executor settings
    DEFAULT_EXECUTOR: str = "virtualenv"
    DOCKER_IMAGE: str = "python:3.11-slim"
    
    # Cleanup settings
    CLEANUP_DAYS: int = 7
    
    # Production settings
    DEBUG: bool = False
    TESTING: bool = False
    
    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        # If DATABASE_URL is explicitly set through env vars, respect that
        if isinstance(v, str) and v != "sqlite:///./task_engine.db":
            return v
        
        # Otherwise construct it from components
        if isinstance(v, str) and v.startswith("sqlite"):
            return v
            
        # Make sure all components are available
        postgres_user = values.get('POSTGRES_USER')
        postgres_password = values.get('POSTGRES_PASSWORD')
        postgres_server = values.get('POSTGRES_SERVER')
        postgres_port = values.get('POSTGRES_PORT')
        postgres_db = values.get('POSTGRES_DB')
        
        if None in (postgres_user, postgres_password, postgres_server, postgres_port, postgres_db):
            # Fallback to sqlite if any required component is missing
            return "sqlite:///./task_engine.db"
            
        return f"postgresql://{postgres_user}:{postgres_password}@{postgres_server}:{postgres_port}/{postgres_db}"
    
    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
