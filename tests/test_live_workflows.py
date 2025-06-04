import pytest
import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

class TestLiveWorkflowExecution:
    """Advanced API tests for live workflow execution scenarios"""

    def test_data_processing_workflow(self):
        """Test a realistic data processing workflow"""
        workflow_data = {
            "name": "Data Processing Pipeline",
            "description": "Complete data processing workflow",
            "creator_id": "data_engineer@company.com",
            "tasks": [
                {
                    "name": "Data Validation",
                    "description": "Validate input data",
                    "script_content": """
import json
# Simulate data validation
data = [1, 2, 3, 4, 5]
print(f"Validating {len(data)} records")
assert len(data) > 0, "No data found"
print("Data validation passed")
""",
                    "requirements": [],
                    "order": 0
                },
                {
                    "name": "Data Transformation",
                    "description": "Transform and clean data",
                    "script_content": """
import math
# Transform data
raw_data = [1, 2, 3, 4, 5]
transformed_data = [x * 2 for x in raw_data]
print(f"Transformed data: {transformed_data}")

# Calculate statistics
total = sum(transformed_data)
avg = total / len(transformed_data)
print(f"Total: {total}, Average: {avg}")
""",
                    "requirements": [],
                    "order": 1
                },
                {
                    "name": "Data Export",
                    "description": "Export processed data",
                    "script_content": """
import json
# Simulate data export
processed_data = {"records": 5, "status": "processed", "timestamp": "2025-06-04"}
export_json = json.dumps(processed_data, indent=2)
print("Data export completed:")
print(export_json)
""",
                    "requirements": [],
                    "order": 2
                }
            ]
        }

        # Create and execute the workflow
        response = requests.post(f"{API_BASE}/workflows?mode=run", json=workflow_data)
        assert response.status_code == 200
        
        workflow = response.json()
        assert workflow["name"] == "Data Processing Pipeline"
        assert len(workflow["tasks"]) == 3

        return workflow["id"]

    def test_ml_training_simulation_workflow(self):
        """Test a machine learning training simulation workflow"""
        workflow_data = {
            "name": "ML Training Simulation",
            "description": "Simulate ML model training process",
            "creator_id": "ml_engineer@company.com",
            "tasks": [
                {
                    "name": "Data Preparation",
                    "description": "Prepare training data",
                    "script_content": """
import random
import math

# Simulate data preparation
print("Preparing training data...")
train_size = 1000
test_size = 200

# Generate synthetic data
train_data = [(random.uniform(0, 10), random.uniform(0, 1)) for _ in range(train_size)]
test_data = [(random.uniform(0, 10), random.uniform(0, 1)) for _ in range(test_size)]

print(f"Training set: {len(train_data)} samples")
print(f"Test set: {len(test_data)} samples")
print("Data preparation completed")
""",
                    "requirements": [],
                    "order": 0
                },
                {
                    "name": "Model Training",
                    "description": "Train the model",
                    "script_content": """
import time
import random

print("Starting model training...")

# Simulate training epochs
epochs = 5
for epoch in range(epochs):
    # Simulate training time
    time.sleep(0.5)
    
    # Simulate metrics
    loss = 1.0 - (epoch * 0.15) + random.uniform(-0.05, 0.05)
    accuracy = 0.5 + (epoch * 0.08) + random.uniform(-0.02, 0.02)
    
    print(f"Epoch {epoch + 1}/{epochs} - Loss: {loss:.4f}, Accuracy: {accuracy:.4f}")

print("Model training completed!")
""",
                    "requirements": [],
                    "order": 1
                },
                {
                    "name": "Model Evaluation",
                    "description": "Evaluate model performance",
                    "script_content": """
import random

print("Evaluating model performance...")

# Simulate evaluation metrics
test_accuracy = 0.85 + random.uniform(-0.05, 0.05)
precision = 0.82 + random.uniform(-0.03, 0.03)
recall = 0.88 + random.uniform(-0.04, 0.04)
f1_score = 2 * (precision * recall) / (precision + recall)

print(f"Test Accuracy: {test_accuracy:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall: {recall:.4f}")
print(f"F1 Score: {f1_score:.4f}")

# Model deployment decision
if test_accuracy > 0.8:
    print("✅ Model performance acceptable - Ready for deployment")
else:
    print("❌ Model performance below threshold - Requires retraining")
""",
                    "requirements": [],
                    "order": 2
                }
            ]
        }

        response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert response.status_code == 200
        
        workflow = response.json()
        workflow_id = workflow["id"]

        # Execute the workflow
        execute_response = requests.post(f"{API_BASE}/workflows/{workflow_id}/execute")
        assert execute_response.status_code == 200

        return workflow_id

    def test_web_scraping_workflow(self):
        """Test a web scraping and analysis workflow"""
        workflow_data = {
            "name": "Web Scraping Analysis",
            "description": "Scrape and analyze web data",
            "creator_id": "data_analyst@company.com",
            "tasks": [
                {
                    "name": "URL Validation",
                    "description": "Validate target URLs",
                    "script_content": """
import re

# Simulate URL validation
urls = [
    "https://example.com/api/data",
    "https://api.github.com/users", 
    "https://httpbin.org/json"
]

valid_urls = []
for url in urls:
    # Simple URL validation
    if re.match(r'^https?://', url):
        valid_urls.append(url)
        print(f"✅ Valid URL: {url}")
    else:
        print(f"❌ Invalid URL: {url}")

print(f"Validated {len(valid_urls)} out of {len(urls)} URLs")
""",
                    "requirements": [],
                    "order": 0
                },
                {
                    "name": "Data Collection",
                    "description": "Simulate data collection",
                    "script_content": """
import json
import time

print("Starting data collection...")

# Simulate API responses
responses = []
for i in range(3):
    time.sleep(0.3)  # Simulate network delay
    
    # Mock response data
    response_data = {
        "id": i + 1,
        "name": f"Item {i + 1}",
        "value": (i + 1) * 10,
        "category": "test_data"
    }
    responses.append(response_data)
    print(f"Collected data from source {i + 1}")

print(f"Data collection completed. Collected {len(responses)} records")
""",
                    "requirements": [],
                    "order": 1
                },
                {
                    "name": "Data Analysis",
                    "description": "Analyze collected data",
                    "script_content": """
import statistics

print("Analyzing collected data...")

# Simulate data analysis
data_values = [10, 20, 30]  # From previous step simulation
total_records = len(data_values)
sum_values = sum(data_values)
avg_value = statistics.mean(data_values)
max_value = max(data_values)
min_value = min(data_values)

print(f"Analysis Results:")
print(f"- Total Records: {total_records}")
print(f"- Sum of Values: {sum_values}")
print(f"- Average Value: {avg_value}")
print(f"- Max Value: {max_value}")
print(f"- Min Value: {min_value}")

# Generate report
report = {
    "analysis_date": "2025-06-04",
    "total_records": total_records,
    "summary_stats": {
        "sum": sum_values,
        "average": avg_value,
        "max": max_value,
        "min": min_value
    }
}

print("\\nGenerated Analysis Report:")
print(f"{report}")
""",
                    "requirements": [],
                    "order": 2
                }
            ]
        }

        response = requests.post(f"{API_BASE}/workflows?mode=create", json=workflow_data)
        assert response.status_code == 200
        return response.json()["id"]

    def test_concurrent_workflow_execution(self):
        """Test multiple workflows running concurrently"""
        workflow_ids = []
        
        # Create multiple simple workflows
        for i in range(3):
            workflow_data = {
                "name": f"Concurrent Test Workflow {i+1}",
                "creator_id": f"concurrent_user_{i+1}",
                "tasks": [
                    {
                        "name": f"Concurrent Task {i+1}",
                        "script_content": f"""
import time
import random

print(f"Starting concurrent task {i+1}")
# Simulate some work with random duration
duration = random.uniform(1, 3)
time.sleep(duration)
print(f"Concurrent task {i+1} completed after {{duration:.2f}} seconds")
""",
                        "requirements": [],
                        "order": 0
                    }
                ]
            }
            
            response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
            assert response.status_code == 200
            workflow_ids.append(response.json()["id"])

        # Execute all workflows concurrently
        def execute_workflow(workflow_id):
            return requests.post(f"{API_BASE}/workflows/{workflow_id}/execute")

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(execute_workflow, wf_id) for wf_id in workflow_ids]
            results = [future.result() for future in futures]

        # Verify all executions started successfully
        for result in results:
            assert result.status_code == 200

        return workflow_ids

    def test_workflow_error_handling(self):
        """Test workflow execution with intentional errors"""
        workflow_data = {
            "name": "Error Handling Test",
            "description": "Test error handling in workflow execution",
            "creator_id": "error_test_user",
            "tasks": [
                {
                    "name": "Successful Task",
                    "description": "This task should succeed",
                    "script_content": """
print("This task executes successfully")
result = 2 + 2
print(f"Calculation result: {result}")
""",
                    "requirements": [],
                    "order": 0
                },
                {
                    "name": "Error Task",
                    "description": "This task will cause an error",
                    "script_content": """
print("Starting task that will fail...")
# This will cause a NameError
undefined_variable = some_undefined_variable
print("This line should not be reached")
""",
                    "requirements": [],
                    "order": 1
                },
                {
                    "name": "Recovery Task",
                    "description": "This task should not execute due to previous error",
                    "script_content": """
print("This task should not execute if error handling works correctly")
""",
                    "requirements": [],
                    "order": 2
                }
            ]
        }

        response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert response.status_code == 200
        workflow_id = response.json()["id"]

        # Execute the workflow
        execute_response = requests.post(f"{API_BASE}/workflows/{workflow_id}/execute")
        assert execute_response.status_code == 200

        # Give some time for execution
        time.sleep(3)

        # Check final status
        status_response = requests.get(f"{API_BASE}/workflows/{workflow_id}")
        assert status_response.status_code == 200
        
        # The workflow should show some indication of failure
        workflow_status = status_response.json()
        print(f"Final workflow status: {workflow_status['status']}")

        return workflow_id

    def test_long_running_workflow_monitoring(self):
        """Test monitoring a long-running workflow"""
        workflow_data = {
            "name": "Long Running Workflow",
            "description": "Workflow with extended execution time",
            "creator_id": "monitoring_test_user",
            "tasks": [
                {
                    "name": "Long Running Task",
                    "script_content": """
import time

print("Starting long running process...")
total_steps = 8

for step in range(total_steps):
    print(f"Processing step {step + 1}/{total_steps}")
    time.sleep(1)  # Simulate work
    
    # Show progress
    progress = ((step + 1) / total_steps) * 100
    print(f"Progress: {progress:.1f}%")

print("Long running process completed successfully!")
""",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        # Create and start workflow
        response = requests.post(f"{API_BASE}/workflows?mode=run", json=workflow_data)
        assert response.status_code == 200
        workflow_id = response.json()["id"]

        # Monitor status over time
        statuses = []
        for i in range(5):
            time.sleep(1)
            status_response = requests.get(f"{API_BASE}/workflows/{workflow_id}")
            if status_response.status_code == 200:
                status = status_response.json()["status"]
                statuses.append(status)
                print(f"Status check {i+1}: {status}")

        # Should see status progression
        assert len(statuses) > 0
        return workflow_id

    def test_workflow_resource_usage(self):
        """Test workflow with various resource usage patterns"""
        workflow_data = {
            "name": "Resource Usage Test",
            "description": "Test different resource usage patterns",
            "creator_id": "resource_test_user",
            "tasks": [
                {
                    "name": "CPU Intensive Task",
                    "description": "Simulate CPU intensive work",
                    "script_content": """
import math
import time

print("Starting CPU intensive task...")
start_time = time.time()

# CPU intensive calculation
result = 0
for i in range(100000):
    result += math.sqrt(i)

end_time = time.time()
duration = end_time - start_time

print(f"CPU task completed in {duration:.2f} seconds")
print(f"Final result: {result:.2f}")
""",
                    "requirements": [],
                    "order": 0
                },
                {
                    "name": "Memory Usage Task",
                    "description": "Simulate memory usage",
                    "script_content": """
import sys

print("Testing memory usage...")

# Create some data structures
data_list = list(range(10000))
data_dict = {i: f"value_{i}" for i in range(1000)}
data_string = "x" * 10000

print(f"List size: {len(data_list)} items")
print(f"Dict size: {len(data_dict)} items")
print(f"String size: {len(data_string)} characters")

# Cleanup
del data_list, data_dict, data_string
print("Memory test completed")
""",
                    "requirements": [],
                    "order": 1
                },
                {
                    "name": "I/O Task",
                    "description": "Simulate I/O operations",
                    "script_content": """
import time
import tempfile
import os

print("Testing I/O operations...")

# Simulate file operations
with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
    temp_filename = temp_file.name
    
    # Write data
    for i in range(100):
        temp_file.write(f"Line {i}: This is test data\\n")
    
print(f"Created temporary file: {temp_filename}")

# Read back data
with open(temp_filename, 'r') as temp_file:
    lines = temp_file.readlines()
    print(f"Read {len(lines)} lines from file")

# Cleanup
os.unlink(temp_filename)
print("I/O test completed and cleanup done")
""",
                    "requirements": [],
                    "order": 2
                }
            ]
        }

        response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert response.status_code == 200
        return response.json()["id"]

    def test_workflow_scheduling_info(self):
        """Test creating workflows with scheduling information"""
        workflow_data = {
            "name": "Scheduled Data Backup",
            "description": "Daily data backup workflow",
            "creator_id": "scheduler_user",
            "is_scheduled": True,
            "cron_expression": "0 2 * * *",  # Daily at 2 AM
            "timezone": "UTC",
            "tasks": [
                {
                    "name": "Backup Database",
                    "script_content": """
from datetime import datetime

print("Starting daily backup process...")
backup_time = datetime.now()
print(f"Backup started at: {backup_time}")

# Simulate backup process
import time
time.sleep(1)

print("Database backup completed successfully")
print(f"Backup size: 1.2 GB")
print(f"Backup location: /backups/db_backup_{backup_time.strftime('%Y%m%d_%H%M%S')}.sql")
""",
                    "requirements": [],
                    "order": 0
                }
            ]
        }

        response = requests.post(f"{API_BASE}/workflows", json=workflow_data)
        assert response.status_code == 200
        
        workflow = response.json()
        assert workflow["is_scheduled"] == True
        assert workflow["cron_expression"] == "0 2 * * *"
        assert workflow["timezone"] == "UTC"
        
        return workflow["id"]


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])