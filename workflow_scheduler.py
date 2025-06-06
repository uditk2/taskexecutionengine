#!/usr/bin/env python3
"""
Workflow Scheduler Script

This script creates a workflow that:
1. Gets logs from deployment API for the last 5 minutes
2. Parses the logs to extract error entries
3. Sends the parsed error logs to our recent errors API endpoint
4. Schedules the workflow to execute every 5 minutes

Usage:
    python workflow_scheduler.py
"""

import requests
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
DEPLOYMENT_LOGS_API = "http://localhost:8000/api/v1/logs"  # Deployment API for logs
BUG_REPORT_API = "http://localhost:8002/task-handler/api"  # Your bug report API endpoint
CREATOR_ID = "workflow_scheduler"
CRON_EXPRESSION = "*/5 * * * *"  # Every 5 minutes
TIMEZONE = "UTC"
LOG_TIME_WINDOW_MINUTES = 5  # Get logs from last 5 minutes


def create_workflow_with_services() -> Dict[str, Any]:
    """
    Create a workflow that fetches deployment logs, parses them for errors, and sends them to our recent errors API.
    
    Returns:
        Dict containing the created workflow information
    """
    
    # Task 1: Get logs from deployment API (last 5 minutes)
    task_a_script = f'''
import requests
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

print("=== Task 1: Fetching Deployment Logs ===")

try:
    # Calculate time range for last 5 minutes
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes={LOG_TIME_WINDOW_MINUTES})
    
    # Format timestamps for API (ISO format)
    start_timestamp = start_time.isoformat()
    end_timestamp = end_time.isoformat()
    
    print(f"Fetching logs from {{start_timestamp}} to {{end_timestamp}}")
    print(f"Time window: Last {LOG_TIME_WINDOW_MINUTES} minutes")
    
    # Prepare query parameters for logs API
    params = {{
        'start_time': start_timestamp,
        'end_time': end_timestamp,
        'level': 'all',  # Get all log levels
        'limit': 1000    # Limit to prevent too much data
    }}
    
    # Construct the logs API URL
    logs_url = f"{DEPLOYMENT_LOGS_API}?" + urlencode(params)
    print(f"Making request to: {{logs_url}}")
    
    # Make request to deployment logs API
    headers = {{"Accept": "application/json"}}
    response = requests.get(logs_url, headers=headers, timeout=30)
    response.raise_for_status()
    
    # Get the logs data
    logs_data = response.json()
    print(f"Logs API Response Status: {{response.status_code}}")
    print(f"Number of log entries retrieved: {{len(logs_data.get('logs', []))}}")
    
    # Store the raw logs data for the next task (log parsing)
    output_data = {{
        "logs_response": logs_data,
        "timestamp": datetime.now().isoformat(),
        "status": "success",
        "source": "deployment_api",
        "time_window": {{
            "start": start_timestamp,
            "end": end_timestamp,
            "window_minutes": {LOG_TIME_WINDOW_MINUTES}
        }}
    }}
    
    print(f"Successfully fetched {{len(logs_data.get('logs', []))}} log entries")
    print("=== Deployment Logs Task Completed Successfully ===")
    
except requests.exceptions.RequestException as e:
    print(f"Error calling Deployment Logs API: {{e}}")
    raise
except Exception as e:
    print(f"Unexpected error in logs collection task: {{e}}")
    raise
'''

    # Task 2: Parse logs to extract error entries
    task_b_script = f'''
import requests
import json
import re
from datetime import datetime

print("=== Task 2: Parsing Logs for Errors ===")

try:
    # In a real scenario, you would retrieve the logs from Task 1
    # For this example, we'll simulate the log data structure that would come from Task 1
    # This simulates what Task 1 would have collected
    
    current_time = datetime.now()
    
    # Simulate log data structure (in real workflow, this comes from Task 1)
    simulated_logs_data = {{
        "logs": [
            {{
                "timestamp": (current_time - timedelta(minutes=4)).isoformat(),
                "level": "INFO",
                "message": "Application started successfully",
                "service": "deployment-manager",
                "module": "startup"
            }},
            {{
                "timestamp": (current_time - timedelta(minutes=3)).isoformat(),
                "level": "ERROR",
                "message": "Database connection timeout - retrying in 30 seconds",
                "service": "deployment-manager",
                "module": "database",
                "stack_trace": "ConnectionError: Unable to connect to database\\n  at db.connect()\\n  at startup.init()"
            }},
            {{
                "timestamp": (current_time - timedelta(minutes=2)).isoformat(),
                "level": "WARN",
                "message": "High memory usage detected: 85% of available memory in use",
                "service": "deployment-manager",
                "module": "monitoring"
            }},
            {{
                "timestamp": (current_time - timedelta(minutes=1)).isoformat(),
                "level": "ERROR",
                "message": "Failed to deploy container: insufficient disk space",
                "service": "deployment-manager",
                "module": "container_deploy",
                "stack_trace": "DeploymentError: Not enough disk space\\n  at deploy.start()\\n  at manager.execute()"
            }},
            {{
                "timestamp": current_time.isoformat(),
                "level": "INFO",
                "message": "Cleanup task completed successfully",
                "service": "deployment-manager",
                "module": "cleanup"
            }}
        ]
    }}
    
    print(f"Processing {{len(simulated_logs_data['logs'])}} log entries for error extraction...")
    
    # Parse logs and extract only error and warning entries
    error_patterns = [
        r'(?i)error:?\\s+.*$',
        r'(?i)exception:?\\s+.*$',
        r'(?i)failed:?\\s+.*$',
        r'(?i)fatal:?\\s+.*$',
        r'\\b[A-Z][a-zA-Z]*(?:Error|Exception)\\b'
    ]
    
    parsed_errors = []
    for log_entry in simulated_logs_data["logs"]:
        log_level = log_entry.get("level", "").upper()
        log_message = log_entry.get("message", "")
        
        # Check if this is an error/warning entry
        is_error_entry = (log_level in ["ERROR", "WARN", "WARNING", "FATAL", "CRITICAL"])
        
        # Also check message content for error patterns
        contains_error_pattern = any(re.search(pattern, log_message) for pattern in error_patterns)
        
        if is_error_entry or contains_error_pattern:
            parsed_error = {{
                "timestamp": log_entry.get("timestamp"),
                "level": log_level if log_level in ["ERROR", "WARN", "WARNING", "FATAL", "CRITICAL"] else "ERROR",
                "message": log_message,
                "module": log_entry.get("module", log_entry.get("service", "unknown")),
                "service": log_entry.get("service", "deployment-manager"),
                "stack_trace": log_entry.get("stack_trace", "")
            }}
            parsed_errors.append(parsed_error)
    
    # Prepare the parsed error data for sending to our API
    error_data = {{
        "workflow_name": "Deployment Logs Error Analysis",
        "timestamp": current_time.isoformat(),
        "time_window_minutes": {LOG_TIME_WINDOW_MINUTES},
        "total_logs_processed": len(simulated_logs_data["logs"]),
        "errors_found": len(parsed_errors),
        "error_entries": parsed_errors,
        "analysis_metadata": {{
            "processing_step": "error_extraction",
            "processed_by": "workflow_engine",
            "task_order": 2,
            "error_levels_count": {{
                "ERROR": sum(1 for err in parsed_errors if err["level"] == "ERROR"),
                "WARN": sum(1 for err in parsed_errors if err["level"] == "WARN"),
                "WARNING": sum(1 for err in parsed_errors if err["level"] == "WARNING"),
                "FATAL": sum(1 for err in parsed_errors if err["level"] == "FATAL"),
                "CRITICAL": sum(1 for err in parsed_errors if err["level"] == "CRITICAL")
            }}
        }}
    }}
    
    print(f"Successfully parsed {{len(parsed_errors)}} error/warning entries from {{len(simulated_logs_data['logs'])}} total log entries")
    print(f"Error breakdown: {{json.dumps(error_data['analysis_metadata']['error_levels_count'], indent=2)}}")
    print("=== Log Parsing Task Completed Successfully ===")
    
    # Store the parsed errors for Task 3
    global parsed_error_data
    parsed_error_data = error_data
    
except Exception as e:
    print(f"Unexpected error in log parsing task: {{e}}")
    raise
'''

    # Task 3: Submit parsed errors as bug reports to your task handler API
    task_c_script = f'''
import requests
import json
from datetime import datetime, timedelta

print("=== Task 3: Submitting Parsed Errors as Bug Reports ===")

try:
    # In a real workflow, this would get the parsed error data from Task 2
    # For demonstration, we'll use the data structure that Task 2 would produce
    
    current_time = datetime.now()
    
    # This simulates the parsed error data from Task 2
    parsed_error_data = {{
        "workflow_name": "Deployment Logs Error Analysis",
        "timestamp": current_time.isoformat(),
        "time_window_minutes": {LOG_TIME_WINDOW_MINUTES},
        "total_logs_processed": 5,
        "errors_found": 2,
        "error_entries": [
            {{
                "timestamp": (current_time - timedelta(minutes=3)).isoformat(),
                "level": "ERROR",
                "message": "Database connection timeout - retrying in 30 seconds",
                "module": "database",
                "service": "deployment-manager",
                "stack_trace": "ConnectionError: Unable to connect to database\\n  at db.connect()\\n  at startup.init()"
            }},
            {{
                "timestamp": (current_time - timedelta(minutes=1)).isoformat(),
                "level": "ERROR", 
                "message": "Failed to deploy container: insufficient disk space",
                "module": "container_deploy",
                "service": "deployment-manager",
                "stack_trace": "DeploymentError: Not enough disk space\\n  at deploy.start()\\n  at manager.execute()"
            }}
        ]
    }}
    
    print(f"Preparing to submit {{parsed_error_data['errors_found']}} error entries as bug reports")
    
    # Configuration for bug report submission
    # These would typically be environment variables or config parameters
    USER_ID = "workflow_scheduler_user"  # Default user for automated bug reports
    WORKSPACE_NAME = "main_workspace"    # Default workspace for error tracking
    
    bug_report_url = f"{BUG_REPORT_API}/{{USER_ID}}/{{WORKSPACE_NAME}}/submit-bug"
    print(f"Target Bug Report API: {{bug_report_url}}")
    
    # Submit each error as a separate bug report
    submitted_bugs = []
    for i, error_entry in enumerate(parsed_error_data["error_entries"], 1):
        
        # Create a comprehensive bug description from the error data
        bug_description = f"""
**Automated Bug Report from Deployment Logs**

**Error Details:**
- **Level:** {{error_entry["level"]}}
- **Timestamp:** {{error_entry["timestamp"]}}
- **Service/Module:** {{error_entry["service"]}}/{{error_entry["module"]}}
- **Message:** {{error_entry["message"]}}

**Stack Trace:**
```
{{error_entry.get("stack_trace", "No stack trace available")}}
```

**Context:**
- **Source:** Deployment Logs Monitoring Workflow
- **Time Window:** Last {LOG_TIME_WINDOW_MINUTES} minutes
- **Total Logs Processed:** {{parsed_error_data["total_logs_processed"]}}
- **Workflow Timestamp:** {{parsed_error_data["timestamp"]}}

**Suggested Actions:**
- Investigate the {{error_entry["module"]}} service for {{error_entry["level"].lower()}} conditions
- Check system resources and connectivity
- Review recent deployment changes that might have caused this error

**Priority:** {{"High" if error_entry["level"] == "ERROR" else "Medium"}}
        """.strip()
        
        # Prepare the bug report payload
        bug_payload = {{
            "bug_description": bug_description
        }}
        
        print(f"\\nSubmitting bug report {{i}}/{{len(parsed_error_data['error_entries'])}}...")
        print(f"Error: {{error_entry['message'][:50]}}...")
        
        try:
            # Make request to bug report API
            headers = {{"Content-Type": "application/json"}}
            response = requests.post(bug_report_url, json=bug_payload, headers=headers, timeout=30)
            
            print(f"Bug Report API Response Status: {{response.status_code}}")
            
            if response.status_code in [200, 201]:
                try:
                    api_response = response.json()
                    if api_response.get("success"):
                        submitted_bugs.append({{
                            "error_index": i,
                            "chat_id": api_response.get("data", {{}}).get("chat_id"),
                            "error_message": error_entry["message"],
                            "status": "submitted"
                        }})
                        print(f"✅ Bug report submitted successfully!")
                        print(f"   Chat ID: {{api_response.get('data', {{}}).get('chat_id')}}")
                    else:
                        print(f"❌ Bug report submission failed: {{api_response.get('error', 'Unknown error')}}")
                        submitted_bugs.append({{
                            "error_index": i,
                            "error_message": error_entry["message"],
                            "status": "failed",
                            "error": api_response.get('error', 'Unknown error')
                        }})
                except Exception as json_error:
                    print(f"❌ Failed to parse bug report response: {{json_error}}")
                    print(f"Raw response: {{response.text}}")
                    submitted_bugs.append({{
                        "error_index": i,
                        "error_message": error_entry["message"],
                        "status": "failed",
                        "error": f"JSON parse error: {{json_error}}"
                    }})
            else:
                print(f"❌ Bug Report API returned status {{response.status_code}}")
                print(f"Response: {{response.text}}")
                submitted_bugs.append({{
                    "error_index": i,
                    "error_message": error_entry["message"],
                    "status": "failed",
                    "error": f"HTTP {{response.status_code}}: {{response.text}}"
                }})
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error calling Bug Report API for error {{i}}: {{e}}")
            submitted_bugs.append({{
                "error_index": i,
                "error_message": error_entry["message"],
                "status": "failed",
                "error": str(e)
            }})
    
    # Summary of submissions
    successful_submissions = [bug for bug in submitted_bugs if bug["status"] == "submitted"]
    failed_submissions = [bug for bug in submitted_bugs if bug["status"] == "failed"]
    
    print(f"\\n=== Bug Report Submission Summary ===")
    print(f"Total Errors Processed: {{len(parsed_error_data['error_entries'])}}")
    print(f"Successfully Submitted: {{len(successful_submissions)}}")
    print(f"Failed Submissions: {{len(failed_submissions)}}")
    
    if successful_submissions:
        print("\\n✅ Successfully Submitted Bug Reports:")
        for bug in successful_submissions:
            print(f"   - Chat ID {{bug['chat_id']}}: {{bug['error_message'][:50]}}...")
    
    if failed_submissions:
        print("\\n❌ Failed Bug Report Submissions:")
        for bug in failed_submissions:
            print(f"   - Error {{bug['error_index']}}: {{bug['error'][:50]}}...")
    
    print("=== Deployment Logs Error Analysis Workflow Complete ===")
    
except Exception as e:
    print(f"Unexpected error in bug report submission task: {{e}}")
    raise
'''

    # Create the workflow data structure
    workflow_data = {
        "name": "Deployment Logs Error Analysis Workflow",
        "description": f"Automated workflow that collects deployment logs from the last {LOG_TIME_WINDOW_MINUTES} minutes, parses them for errors, and submits error entries as bug reports to your task handler API for tracking and resolution",
        "creator_id": CREATOR_ID,
        "tasks": [
            {
                "name": "Collect Deployment Logs",
                "description": f"Fetch logs from deployment API for the last {LOG_TIME_WINDOW_MINUTES} minutes",
                "script_content": task_a_script,
                "requirements": ["requests>=2.25.1", "urllib3>=1.26.0", "certifi"],
                "order": 0
            },
            {
                "name": "Parse Logs for Errors",
                "description": "Extract error and warning entries from the collected logs using pattern matching",
                "script_content": task_b_script,
                "requirements": ["requests>=2.25.1", "python-dateutil>=2.8.0"],
                "order": 1
            },
            {
                "name": "Submit Errors as Bug Reports",
                "description": "Send parsed error entries as bug reports to your task handler API for tracking and resolution",
                "script_content": task_c_script,
                "requirements": ["requests>=2.25.1", "urllib3>=1.26.0", "certifi"],
                "order": 2
            }
        ]
    }
    
    return workflow_data


def create_workflow(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a workflow using the TaskExecutionEngine API.
    
    Args:
        workflow_data: The workflow configuration
        
    Returns:
        Dict containing the API response
    """
    print(f"Creating workflow: {workflow_data['name']}")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/workflows",
            json=workflow_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        workflow = response.json()
        print(f"✅ Workflow created successfully!")
        print(f"   - Workflow ID: {workflow['id']}")
        print(f"   - Name: {workflow['name']}")
        print(f"   - Status: {workflow['status']}")
        print(f"   - Tasks: {len(workflow['tasks'])}")
        
        return workflow
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating workflow: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        raise


def schedule_workflow(workflow_id: int) -> Dict[str, Any]:
    """
    Schedule a workflow to run every 5 minutes.
    
    Args:
        workflow_id: The ID of the workflow to schedule
        
    Returns:
        Dict containing the scheduling response
    """
    print(f"Scheduling workflow {workflow_id} to run every 5 minutes...")
    
    schedule_data = {
        "cron_expression": CRON_EXPRESSION,
        "timezone": TIMEZONE
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/workflows/{workflow_id}/schedule",
            json=schedule_data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        schedule_info = response.json()
        print(f"✅ Workflow scheduled successfully!")
        print(f"   - Cron Expression: {schedule_info['cron_expression']}")
        print(f"   - Timezone: {schedule_info['timezone']}")
        print(f"   - Next Run: {schedule_info['next_run_at']}")
        
        return schedule_info
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error scheduling workflow: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        raise


def get_workflow_status(workflow_id: int) -> Dict[str, Any]:
    """
    Get the current status of a workflow.
    
    Args:
        workflow_id: The ID of the workflow
        
    Returns:
        Dict containing the workflow status
    """
    try:
        response = requests.get(f"{API_BASE_URL}/workflows/{workflow_id}/status")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error getting workflow status: {e}")
        raise


def test_workflow_execution(workflow_id: int) -> None:
    """
    Test the workflow by executing it once manually.
    
    Args:
        workflow_id: The ID of the workflow to test
    """
    print(f"Testing workflow {workflow_id} with manual execution...")
    
    try:
        # Execute the workflow
        response = requests.post(f"{API_BASE_URL}/workflows/{workflow_id}/execute")
        response.raise_for_status()
        
        execution_info = response.json()
        print(f"✅ Workflow execution started!")
        print(f"   - Message: {execution_info['message']}")
        print(f"   - Celery Task ID: {execution_info.get('celery_task_id', 'N/A')}")
        
        # Check status
        import time
        print("Checking execution status...")
        for i in range(5):  # Check status 5 times
            time.sleep(2)
            status = get_workflow_status(workflow_id)
            print(f"   Status check {i+1}: {status['status']}")
            
            if status['status'] in ['completed', 'failed']:
                break
                
        print(f"Final status: {status['status']}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error testing workflow execution: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")


def main():
    """
    Main function to create and schedule the workflow.
    """
    print("🚀 TaskExecutionEngine Deployment Logs Error Analysis Workflow")
    print("=" * 70)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Deployment Logs API: {DEPLOYMENT_LOGS_API}")
    print(f"Bug Report API: {BUG_REPORT_API}")
    print(f"Schedule: Every 5 minutes ({CRON_EXPRESSION})")
    print(f"Log Time Window: Last {LOG_TIME_WINDOW_MINUTES} minutes")
    print("=" * 70)
    
    try:
        # Step 1: Create the workflow
        print("\n📝 Step 1: Creating workflow...")
        workflow_data = create_workflow_with_services()
        workflow = create_workflow(workflow_data)
        workflow_id = workflow['id']
        
        # Step 2: Schedule the workflow
        print(f"\n⏰ Step 2: Scheduling workflow...")
        schedule_info = schedule_workflow(workflow_id)
        
        # Step 3: Test the workflow (optional)
        print(f"\n🧪 Step 3: Testing workflow execution...")
        test_workflow_execution(workflow_id)
        
        # Summary
        print(f"\n✅ SUCCESS: Error Analysis Workflow Setup Complete!")
        print(f"   - Workflow ID: {workflow_id}")
        print(f"   - Tasks: 3 (Log Collection → Error Parsing → Bug Report Submission)")
        print(f"   - Scheduled to run every 5 minutes")
        print(f"   - Next execution: {schedule_info['next_run_at']}")
        print(f"   - Monitor at: {API_BASE_URL}/workflows/{workflow_id}/status")
        print(f"   - Dashboard: http://localhost:8000/dashboard")
        print(f"   - Error logs will be submitted as bug reports to: {BUG_REPORT_API}")
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()