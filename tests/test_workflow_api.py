import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestWorkflowAPI:
    """Test suite for workflow creation API"""

    def test_create_workflow_create_mode(self):
        workflow_data = {
            "name": "Test Workflow",
            "description": "A test workflow",
            "creator_id": "test_user",
            "tasks": [
                {
                    "name": "Test Task",
                    "description": "A test task",
                    "script_content": "print('Hello, World!')",
                    "requirements": [],
                    "order": 1
                }
            ]
        }
        response = client.post("/api/v1/workflows?mode=create", json=workflow_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Workflow"
        assert data["creator_id"] == "test_user"
        assert data["status"] == "pending"
        assert data["status_url"] is not None
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["name"] == "Test Task"

    def test_create_workflow_run_mode(self):
        workflow_data = {
            "name": "Execute Workflow",
            "description": "A workflow to execute immediately",
            "creator_id": "test_user",
            "tasks": [
                {
                    "name": "Quick Task",
                    "script_content": "print('Executing immediately')",
                    "requirements": [],
                    "order": 1
                }
            ]
        }
        response = client.post("/api/v1/workflows?mode=run", json=workflow_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Execute Workflow"
        assert data["status"] == "running"
        assert data["celery_task_id"] is not None
        assert data["status_url"] is not None

    def test_create_workflow_with_dependencies(self):
        workflow_data = {
            "name": "Dependency Workflow",
            "creator_id": "test_user",
            "tasks": [
                {
                    "name": "Pandas Task",
                    "script_content": "import pandas as pd\nprint('Pandas imported successfully')",
                    "requirements": ["pandas"],
                    "order": 1
                }
            ]
        }
        response = client.post("/api/v1/workflows?mode=create", json=workflow_data)
        assert response.status_code == 200
        data = response.json()
        assert data["tasks"][0]["requirements"] == ["pandas"]

    def test_create_workflow_invalid_mode(self):
        workflow_data = {
            "name": "Invalid Mode Workflow",
            "creator_id": "test_user",
            "tasks": []
        }
        response = client.post("/api/v1/workflows?mode=invalid", json=workflow_data)
        assert response.status_code == 400
        assert "Mode must be 'create' or 'run'" in response.json()["detail"]

    def test_create_workflow_missing_required_fields(self):
        workflow_data = {"name": "Incomplete Workflow"}
        response = client.post("/api/v1/workflows", json=workflow_data)
        assert response.status_code == 422

    def test_get_workflow_status(self):
        workflow_data = {
            "name": "Status Test Workflow",
            "creator_id": "test_user",
            "tasks": [
                {
                    "name": "Status Task",
                    "script_content": "print('Status test')",
                    "requirements": [],
                    "order": 1
                }
            ]
        }
        create_response = client.post("/api/v1/workflows?mode=create", json=workflow_data)
        assert create_response.status_code == 200
        workflow_id = create_response.json()["id"]
        status_response = client.get(f"/api/v1/workflows/{workflow_id}/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["id"] == workflow_id
        assert status_data["name"] == "Status Test Workflow"
        assert "tasks" in status_data

    def test_workflow_persistence(self):
        workflow_data = {
            "name": "Persistence Test",
            "creator_id": "test_user",
            "tasks": [
                {
                    "name": "Persist Task",
                    "script_content": "print('Testing persistence')",
                    "requirements": ["requests"],
                    "order": 1
                }
            ]
        }
        response = client.post("/api/v1/workflows", json=workflow_data)
        assert response.status_code == 200
        workflow_id = response.json()["id"]
        get_response = client.get(f"/api/v1/workflows/{workflow_id}")
        assert get_response.status_code == 200
        retrieved_workflow = get_response.json()
        assert retrieved_workflow["name"] == "Persistence Test"
        assert len(retrieved_workflow["tasks"]) == 1
        assert retrieved_workflow["tasks"][0]["requirements"] == ["requests"]


if __name__ == "__main__":
    pytest.main([__file__])
