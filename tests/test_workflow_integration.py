import pytest
import time
import requests
import json
from typing import Dict, Any

# Configuration for API tests
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

class TestWorkflowAPIIntegration:
    """Simple API-based integration tests for workflow creation and execution"""

    def test_workflow_creation_basic(self):
        """Test basic workflow creation via API"""
        workflow_data = {
            "name": "Basic API Test Workflow",
            "description": "Testing workflow creation through API",
            "creator_id": "api_test_user",
            "tasks": [
                {
                    "name": "Simple Print Task",
                    "description": "Print a simple message",
                    "script_content": "print('Hello from API test!')",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert response.status_code == 200
        
        workflow = response.json()
        assert workflow["name"] == "Basic API Test Workflow"
        assert workflow["status"] == "pending"
        assert len(workflow["tasks"]) == 1
        assert "id" in workflow
        
        return workflow["id"]

    def test_workflow_execution(self):
        """Test workflow execution via API"""
        # First create a workflow
        workflow_id = self.test_workflow_creation_basic()
        
        # Execute the workflow
        execute_response = requests.post(f"{API_BASE}/workflows/{workflow_id}/execute")
        assert execute_response.status_code == 200
        
        execute_data = execute_response.json()
        assert "message" in execute_data
        assert "Workflow execution started" in execute_data["message"]

    def test_workflow_status_monitoring(self):
        """Test monitoring workflow status during execution"""
        # Create workflow
        workflow_data = {
            "name": "Status Monitoring Test",
            "creator_id": "api_test_user",
            "tasks": [
                {
                    "name": "Quick Task",
                    "script_content": "import time\nprint('Starting task')\ntime.sleep(2)\nprint('Task completed')",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        create_response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert create_response.status_code == 200
        workflow_id = create_response.json()["id"]

        # Execute workflow
        execute_response = requests.post(f"{API_BASE}/workflows/{workflow_id}/execute")
        assert execute_response.status_code == 200

        # Monitor status
        status_response = requests.get(f"{API_BASE}/workflows/{workflow_id}")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        assert status_data["status"] in ["running", "completed", "pending"]

    def test_multi_task_workflow(self):
        """Test workflow with multiple sequential tasks"""
        workflow_data = {
            "name": "Multi-Task API Test",
            "description": "Testing multiple tasks in sequence",
            "creator_id": "api_test_user",
            "tasks": [
                {
                    "name": "Task 1",
                    "description": "First task",
                    "script_content": "print('Executing Task 1')\nx = 5",
                    "requirements": [],
                    "order": 0
                },
                {
                    "name": "Task 2", 
                    "description": "Second task",
                    "script_content": "print('Executing Task 2')\ny = 10",
                    "requirements": [],
                    "order": 1
                },
                {
                    "name": "Task 3",
                    "description": "Third task", 
                    "script_content": "print('Executing Task 3')\nprint('All tasks completed!')",
                    "requirements": [],
                    "order": 2
                }
            ]
        }

        response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert response.status_code == 200
        
        workflow = response.json()
        assert len(workflow["tasks"]) == 3
        
        # Verify task ordering
        tasks = sorted(workflow["tasks"], key=lambda t: t["order"])
        assert tasks[0]["name"] == "Task 1"
        assert tasks[1]["name"] == "Task 2"
        assert tasks[2]["name"] == "Task 3"

    def test_workflow_list_api(self):
        """Test listing workflows via API"""
        # Create a couple of workflows first
        for i in range(2):
            workflow_data = {
                "name": f"List Test Workflow {i+1}",
                "creator_id": "list_test_user",
                "tasks": [
                    {
                        "name": f"Task {i+1}",
                        "script_content": f"print('Task {i+1} executed')",
                        "requirements": [],
                        "order": 0
                    }
                ]
            }
            requests.post(f"{API_BASE}/workflows", json=workflow_data)

        # List all workflows
        list_response = requests.get(f"{API_BASE}/workflows/")
        assert list_response.status_code == 200
        
        workflows = list_response.json()
        assert isinstance(workflows, list)
        assert len(workflows) >= 2

    def test_workflow_filtering_by_status(self):
        """Test filtering workflows by status"""
        # Create a workflow
        workflow_data = {
            "name": "Filter Test Workflow",
            "creator_id": "filter_test_user",
            "tasks": [
                {
                    "name": "Filter Task",
                    "script_content": "print('Testing status filtering')",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        create_response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert create_response.status_code == 200

        # Filter by pending status
        pending_response = requests.get(f"{API_BASE}/workflows/?status=pending")
        assert pending_response.status_code == 200
        
        pending_workflows = pending_response.json()
        assert isinstance(pending_workflows, list)
        # Should contain at least the workflow we just created
        assert len(pending_workflows) >= 1

    def test_workflow_creation_with_dependencies(self):
        """Test creating workflow with Python package dependencies"""
        workflow_data = {
            "name": "Dependencies Test Workflow",
            "description": "Testing workflow with dependencies",
            "creator_id": "deps_test_user", 
            "tasks": [
                {
                    "name": "JSON Task",
                    "description": "Task using json module",
                    "script_content": """
import json
data = {'test': 'value', 'number': 42}
json_string = json.dumps(data)
print(f'JSON output: {json_string}')
""",
                    "requirements": [],
                    "order": 0
                },
                {
                    "name": "Math Task",
                    "description": "Task using math module",
                    "script_content": """
import math
result = math.sqrt(16)
print(f'Square root of 16 is: {result}')
""",
                    "requirements": [],
                    "order": 1
                }
            ]
        }

        response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert response.status_code == 200
        
        workflow = response.json()
        assert workflow["name"] == "Dependencies Test Workflow"
        assert len(workflow["tasks"]) == 2

    def test_workflow_update_api(self):
        """Test updating workflow via API"""
        # Create initial workflow
        workflow_data = {
            "name": "Original Workflow Name",
            "description": "Original description",
            "creator_id": "update_test_user",
            "tasks": [
                {
                    "name": "Original Task",
                    "script_content": "print('Original task')",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        create_response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert create_response.status_code == 200
        workflow_id = create_response.json()["id"]

        # Update workflow
        update_data = {
            "name": "Updated Workflow Name",
            "description": "Updated description"
        }

        update_response = requests.put(f"{API_BASE}/workflows/{workflow_id}", json=update_data)
        assert update_response.status_code == 200
        
        updated_workflow = update_response.json()
        assert updated_workflow["name"] == "Updated Workflow Name"
        assert updated_workflow["description"] == "Updated description"

    def test_workflow_deletion_api(self):
        """Test deleting workflow via API"""
        # Create workflow to delete
        workflow_data = {
            "name": "To Be Deleted",
            "creator_id": "delete_test_user",
            "tasks": [
                {
                    "name": "Delete Test Task",
                    "script_content": "print('This will be deleted')",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        create_response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert create_response.status_code == 200
        workflow_id = create_response.json()["id"]

        # Verify it exists
        get_response = requests.get(f"{API_BASE}/workflows/{workflow_id}")
        assert get_response.status_code == 200

        # Delete workflow
        delete_response = requests.delete(f"{API_BASE}/workflows/{workflow_id}")
        assert delete_response.status_code == 200

        # Verify it's gone
        get_response_after = requests.get(f"{API_BASE}/workflows/{workflow_id}")
        assert get_response_after.status_code == 404

    def test_error_handling_invalid_workflow_id(self):
        """Test error handling for invalid workflow ID"""
        invalid_id = 999999

        # Try to get non-existent workflow
        get_response = requests.get(f"{API_BASE}/workflows/{invalid_id}")
        assert get_response.status_code == 404

        # Try to execute non-existent workflow
        execute_response = requests.post(f"{API_BASE}/workflows/{invalid_id}/execute")
        assert execute_response.status_code == 404

        # Try to delete non-existent workflow
        delete_response = requests.delete(f"{API_BASE}/workflows/{invalid_id}")
        assert delete_response.status_code == 404

    def test_workflow_creation_validation(self):
        """Test validation for workflow creation"""
        # Test with missing required fields
        invalid_data = {
            "description": "Missing name and creator_id"
        }

        response = requests.post(f"{API_BASE}/workflows", json=invalid_data)
        assert response.status_code == 422

        # Test with empty name
        invalid_data2 = {
            "name": "",
            "creator_id": "test_user",
            "tasks": []
        }

        response2 = requests.post(f"{API_BASE}/workflows", json=invalid_data2)
        assert response2.status_code == 422

    def test_workflow_execution_and_cancellation(self):
        """Test workflow execution followed by cancellation"""
        # Create workflow with longer running task
        workflow_data = {
            "name": "Cancellation Test",
            "creator_id": "cancel_test_user",
            "tasks": [
                {
                    "name": "Long Running Task",
                    "script_content": """
import time
print('Starting long running task...')
for i in range(5):
    print(f'Step {i+1}/5')
    time.sleep(1)
print('Task completed')
""",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        create_response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert create_response.status_code == 200
        workflow_id = create_response.json()["id"]

        # Start execution
        execute_response = requests.post(f"{API_BASE}/workflows/{workflow_id}/execute")
        assert execute_response.status_code == 200

        # Give it a moment to start
        time.sleep(1)

        # Cancel workflow
        cancel_response = requests.post(f"{API_BASE}/workflows/{workflow_id}/cancel")
        assert cancel_response.status_code == 200
        
        cancel_data = cancel_response.json()
        assert "message" in cancel_data

    def test_workflow_create_and_run_mode(self):
        """Test creating and running workflow in one API call"""
        workflow_data = {
            "name": "Create and Run Test",
            "description": "Test immediate execution",
            "creator_id": "create_run_test_user",
            "tasks": [
                {
                    "name": "Immediate Execution Task",
                    "script_content": "print('This workflow was created and executed immediately')",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        # Use mode=run to create and execute in one step
        response = requests.post(f"{API_BASE}/workflows?mode=run", json=workflow_data)
        assert response.status_code == 200
        
        workflow = response.json()
        assert workflow["name"] == "Create and Run Test"
        assert workflow["status"] in ["running", "completed"]
        assert "celery_task_id" in workflow or workflow["status"] == "completed"

    def test_workflow_pagination(self):
        """Test workflow list pagination"""
        # Create several workflows
        for i in range(3):
            workflow_data = {
                "name": f"Pagination Test Workflow {i+1}",
                "creator_id": "pagination_user",
                "tasks": [
                    {
                        "name": f"Pagination Task {i+1}",
                        "script_content": f"print('Pagination test {i+1}')",
                        "requirements": [],
                        "order": 0
                    }
                ]
            }
            requests.post(f"{API_BASE}/workflows", json=workflow_data)

        # Test pagination parameters
        page1_response = requests.get(f"{API_BASE}/workflows/?skip=0&limit=2")
        assert page1_response.status_code == 200
        page1_data = page1_response.json()
        assert len(page1_data) <= 2

        page2_response = requests.get(f"{API_BASE}/workflows/?skip=2&limit=2")
        assert page2_response.status_code == 200
        page2_data = page2_response.json()
        assert isinstance(page2_data, list)

    def test_workflow_creator_filtering(self):
        """Test filtering workflows by creator"""
        creator_id = "creator_filter_test@example.com"
        
        # Create workflow with specific creator
        workflow_data = {
            "name": "Creator Filter Test",
            "creator_id": creator_id,
            "tasks": [
                {
                    "name": "Creator Test Task",
                    "script_content": "print('Testing creator filtering')",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        create_response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert create_response.status_code == 200

        # Filter by creator
        filter_response = requests.get(f"{API_BASE}/workflows/?creator_id={creator_id}")
        assert filter_response.status_code == 200
        
        filtered_workflows = filter_response.json()
        assert isinstance(filtered_workflows, list)
        assert len(filtered_workflows) >= 1
        
        # Verify all returned workflows have the correct creator
        for workflow in filtered_workflows:
            assert workflow["creator_id"] == creator_id


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])