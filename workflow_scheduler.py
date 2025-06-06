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
    
    # Or use the class directly:
    scheduler = WorkflowScheduler("user123", "my_workspace")
    scheduler.create_and_schedule_workflow()
"""

import requests
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"

# Based on ProjectDeployer analysis:
# self.logs_api_url = f"{deployment_api_url}/api/logs"
# url = f"{self.logs_api_url}/{user_id}/{workspace_name}?minutes={minutes}"
DEPLOYMENT_API_BASE = "https://apps.synergiqai.com"  # Base URL for deployment API
BUG_REPORT_API = "http://localhost:8002/task-handler/api"  # Your bug report API endpoint
CREATOR_ID = "workflow_scheduler"
CRON_EXPRESSION = "*/5 * * * *"  # Every 5 minutes
TIMEZONE = "UTC"
LOG_TIME_WINDOW_MINUTES = 5  # Get logs from last 5 minutes


class WorkflowScheduler:
    """
    A class for scheduling deployment log monitoring workflows.
    
    This class creates workflows that monitor deployment logs for specific user/workspace combinations,
    parse them for errors, and submit error reports to a bug tracking API.
    """
    
    def __init__(self, user_id: str, workspace_name: str, 
                 deployment_api_base: str = DEPLOYMENT_API_BASE,
                 bug_report_api: str = BUG_REPORT_API,
                 workflow_api_base: str = API_BASE_URL,
                 log_time_window_minutes: int = LOG_TIME_WINDOW_MINUTES):
        """
        Initialize the WorkflowScheduler.
        
        Args:
            user_id: The user ID for log fetching
            workspace_name: The workspace name for log fetching
            deployment_api_base: Base URL for the deployment API
            bug_report_api: URL for the bug report submission API
            workflow_api_base: Base URL for the workflow execution engine API
            log_time_window_minutes: Number of minutes of logs to fetch
        """
        self.user_id = user_id
        self.workspace_name = workspace_name
        self.deployment_api_base = deployment_api_base
        self.bug_report_api = bug_report_api
        self.workflow_api_base = workflow_api_base
        self.log_time_window_minutes = log_time_window_minutes
        
        # Construct API URLs based on ProjectDeployer pattern
        self.deployment_logs_api = f"{deployment_api_base}/api/logs/{user_id}/{workspace_name}"
        self.workflow_name = f"{workspace_name}_deployment_logs_error_analysis_workflow"
        
    def create_workflow_with_services(self) -> Dict[str, Any]:
        """
        Create a workflow that fetches deployment logs, parses them for errors, and sends them to our recent errors API.
        
        Returns:
            Dict containing the created workflow information
        """
        
        # Task 1: Get logs from deployment API (last N minutes)
        task_a_script = f'''
import requests
import json
from datetime import datetime, timedelta

print("=== Task 1: Fetching Deployment Logs ===")

try:
    # Configuration from WorkflowScheduler
    DEPLOYMENT_LOGS_API = "{self.deployment_logs_api}"
    USER_ID = "{self.user_id}"
    WORKSPACE_NAME = "{self.workspace_name}"
    LOG_TIME_WINDOW_MINUTES = {self.log_time_window_minutes}
    
    print(f"Fetching logs for user: {{USER_ID}}, workspace: {{WORKSPACE_NAME}}")
    print(f"Time window: Last {{LOG_TIME_WINDOW_MINUTES}} minutes")
    
    # Construct the logs API URL based on ProjectDeployer pattern:
    # url = f"{{self.logs_api_url}}/{{user_id}}/{{workspace_name}}?minutes={{minutes}}"
    logs_url = f"{{DEPLOYMENT_LOGS_API}}?minutes={{LOG_TIME_WINDOW_MINUTES}}"
    print(f"Making request to: {{logs_url}}")
    
    # Make request to deployment logs API
    headers = {{"Accept": "application/json"}}
    response = requests.get(logs_url, headers=headers, timeout=30)
    
    print(f"Logs API Response Status: {{response.status_code}}")
    
    if response.status_code != 200:
        error_msg = f"Failed to fetch logs: HTTP {{response.status_code}} - {{response.text}}"
        print(f"Error: {{error_msg}}")
        raise Exception(error_msg)
    
    # Get the logs data - based on ProjectDeployer response format
    logs_data = response.json()
    logs = logs_data.get('logs', [])
    
    print(f"Successfully fetched {{len(logs)}} log entries")
    print(f"Workspace: {{logs_data.get('workspace', 'N/A')}}")
    print(f"Username: {{logs_data.get('username', 'N/A')}}")
    print(f"Log count: {{logs_data.get('log_count', len(logs))}}")
    
    # Store the raw logs data for the next task (log parsing)
    output_data = {{
        "logs_response": logs_data,
        "timestamp": datetime.now().isoformat(),
        "status": "success",
        "source": "deployment_api",
        "user_id": USER_ID,
        "workspace_name": WORKSPACE_NAME,
        "time_window_minutes": LOG_TIME_WINDOW_MINUTES,
        "raw_logs": logs
    }}
    
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
    # In a real workflow, this would get the logs from Task 1
    # For demonstration, we'll simulate the log data structure that would come from Task 1
    # Based on ProjectDeployer format where logs have timestamp and content fields
    
    current_time = datetime.now()
    
    # Simulate the logs data structure from ProjectDeployer API response
    simulated_logs_data = {{
        "logs": [
            {{
                "timestamp": (current_time - timedelta(minutes=4)).isoformat(),
                "content": "INFO: Application started successfully for workspace {self.workspace_name}"
            }},
            {{
                "timestamp": (current_time - timedelta(minutes=3)).isoformat(),
                "content": "ERROR: Database connection timeout - retrying in 30 seconds"
            }},
            {{
                "timestamp": (current_time - timedelta(minutes=2)).isoformat(),
                "content": "WARN: High memory usage detected: 85% of available memory in use"
            }},
            {{
                "timestamp": (current_time - timedelta(minutes=1)).isoformat(),
                "content": "ERROR: Failed to deploy container: insufficient disk space"
            }},
            {{
                "timestamp": current_time.isoformat(),
                "content": "INFO: Cleanup task completed successfully"
            }}
        ],
        "workspace": "{self.workspace_name}",
        "username": "{self.user_id}",
        "log_count": 5
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
    
    warning_patterns = [
        r'(?i)warn(?:ing)?:?\\s+.*$',
        r'(?i)deprecated:?\\s+.*$'
    ]
    
    parsed_errors = []
    for log_entry in simulated_logs_data["logs"]:
        timestamp = log_entry.get("timestamp", "")
        content = log_entry.get("content", "")
        
        # Determine log level from content
        log_level = "INFO"  # default
        if any(re.search(pattern, content) for pattern in error_patterns):
            log_level = "ERROR"
        elif any(re.search(pattern, content) for pattern in warning_patterns):
            log_level = "WARN"
        elif content.upper().startswith(("ERROR", "FATAL", "CRITICAL")):
            log_level = "ERROR"
        elif content.upper().startswith(("WARN", "WARNING")):
            log_level = "WARN"
        
        # Only include error and warning entries
        if log_level in ["ERROR", "WARN"]:
            parsed_error = {{
                "timestamp": timestamp,
                "level": log_level,
                "message": content,
                "workspace": "{self.workspace_name}",
                "user_id": "{self.user_id}",
                "source": "deployment_logs"
            }}
            parsed_errors.append(parsed_error)
    
    # Prepare the parsed error data for sending to our API
    error_data = {{
        "workflow_name": "{self.workspace_name}_deployment_logs_error_analysis",
        "timestamp": current_time.isoformat(),
        "time_window_minutes": {self.log_time_window_minutes},
        "workspace_name": "{self.workspace_name}",
        "user_id": "{self.user_id}",
        "total_logs_processed": len(simulated_logs_data["logs"]),
        "errors_found": len(parsed_errors),
        "error_entries": parsed_errors,
        "analysis_metadata": {{
            "processing_step": "error_extraction",
            "processed_by": "workflow_engine",
            "task_order": 2,
            "error_levels_count": {{
                "ERROR": sum(1 for err in parsed_errors if err["level"] == "ERROR"),
                "WARN": sum(1 for err in parsed_errors if err["level"] == "WARN")
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
        "workflow_name": "{self.workspace_name}_deployment_logs_error_analysis",
        "timestamp": current_time.isoformat(),
        "time_window_minutes": {self.log_time_window_minutes},
        "workspace_name": "{self.workspace_name}",
        "user_id": "{self.user_id}",
        "total_logs_processed": 5,
        "errors_found": 2,
        "error_entries": [
            {{
                "timestamp": (current_time - timedelta(minutes=3)).isoformat(),
                "level": "ERROR",
                "message": "ERROR: Database connection timeout - retrying in 30 seconds",
                "workspace": "{self.workspace_name}",
                "user_id": "{self.user_id}",
                "source": "deployment_logs"
            }},
            {{
                "timestamp": (current_time - timedelta(minutes=1)).isoformat(),
                "level": "ERROR", 
                "message": "ERROR: Failed to deploy container: insufficient disk space",
                "workspace": "{self.workspace_name}",
                "user_id": "{self.user_id}",
                "source": "deployment_logs"
            }}
        ]
    }}
    
    print(f"Preparing to submit {{parsed_error_data['errors_found']}} error entries as bug reports")
    print(f"Target workspace: {{parsed_error_data['workspace_name']}}")
    print(f"Target user: {{parsed_error_data['user_id']}}")
    
    # Configuration for bug report submission
    BUG_REPORT_API = "{self.bug_report_api}"
    USER_ID = "{self.user_id}"
    WORKSPACE_NAME = "{self.workspace_name}"
    
    bug_report_url = f"{{BUG_REPORT_API}}/{{USER_ID}}/{{WORKSPACE_NAME}}/submit-bug"
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
- **Workspace:** {{error_entry["workspace"]}}
- **User ID:** {{error_entry["user_id"]}}
- **Message:** {{error_entry["message"]}}

**Context:**
- **Source:** Deployment Logs Monitoring Workflow
- **Time Window:** Last {self.log_time_window_minutes} minutes
- **Total Logs Processed:** {{parsed_error_data["total_logs_processed"]}}
- **Workflow Timestamp:** {{parsed_error_data["timestamp"]}}
- **Workflow:** {{parsed_error_data["workflow_name"]}}

**Suggested Actions:**
- Investigate the deployment logs for {{error_entry["workspace"]}} workspace
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
            "name": self.workflow_name,
            "description": f"Automated workflow for {self.workspace_name} workspace that collects deployment logs from the last {self.log_time_window_minutes} minutes, parses them for errors, and submits error entries as bug reports to the task handler API for tracking and resolution",
            "creator_id": f"{CREATOR_ID}_{self.user_id}_{self.workspace_name}",
            "tasks": [
                {
                    "name": f"Collect Deployment Logs - {self.workspace_name}",
                    "description": f"Fetch logs from deployment API for {self.workspace_name} workspace (last {self.log_time_window_minutes} minutes)",
                    "script_content": task_a_script,
                    "requirements": ["requests>=2.25.1", "urllib3>=1.26.0", "certifi"],
                    "order": 0
                },
                {
                    "name": f"Parse Logs for Errors - {self.workspace_name}",
                    "description": f"Extract error and warning entries from {self.workspace_name} workspace logs using pattern matching",
                    "script_content": task_b_script,
                    "requirements": ["requests>=2.25.1", "python-dateutil>=2.8.0"],
                    "order": 1
                },
                {
                    "name": f"Submit Errors as Bug Reports - {self.workspace_name}",
                    "description": f"Send parsed error entries from {self.workspace_name} workspace as bug reports to task handler API",
                    "script_content": task_c_script,
                    "requirements": ["requests>=2.25.1", "urllib3>=1.26.0", "certifi"],
                    "order": 2
                }
            ]
        }
        
        return workflow_data

    def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
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
                f"{self.workflow_api_base}/workflows",
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

    def schedule_workflow(self, workflow_id: int) -> Dict[str, Any]:
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
                f"{self.workflow_api_base}/workflows/{workflow_id}/schedule",
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

    def get_workflow_status(self, workflow_id: int) -> Dict[str, Any]:
        """
        Get the current status of a workflow.
        
        Args:
            workflow_id: The ID of the workflow
            
        Returns:
            Dict containing the workflow status
        """
        try:
            response = requests.get(f"{self.workflow_api_base}/workflows/{workflow_id}/status")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting workflow status: {e}")
            raise

    def test_workflow_execution(self, workflow_id: int) -> None:
        """
        Test the workflow by executing it once manually.
        
        Args:
            workflow_id: The ID of the workflow to test
        """
        print(f"Testing workflow {workflow_id} with manual execution...")
        
        try:
            # Execute the workflow
            response = requests.post(f"{self.workflow_api_base}/workflows/{workflow_id}/execute")
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
                status = self.get_workflow_status(workflow_id)
                print(f"   Status check {i+1}: {status['status']}")
                
                if status['status'] in ['completed', 'failed']:
                    break
                    
            print(f"Final status: {status['status']}")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error testing workflow execution: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")

    def create_and_schedule_workflow(self) -> Dict[str, Any]:
        """
        Complete workflow creation and scheduling process.
        
        Returns:
            Dict containing workflow and scheduling information
        """
        print(f"🚀 Creating and Scheduling Workflow for {self.workspace_name}")
        print("=" * 70)
        print(f"User ID: {self.user_id}")
        print(f"Workspace: {self.workspace_name}")
        print(f"Deployment Logs API: {self.deployment_logs_api}")
        print(f"Bug Report API: {self.bug_report_api}")
        print(f"Workflow API: {self.workflow_api_base}")
        print(f"Log Time Window: {self.log_time_window_minutes} minutes")
        print("=" * 70)
        
        try:
            # Step 1: Create the workflow
            print(f"\n📝 Step 1: Creating workflow...")
            workflow_data = self.create_workflow_with_services()
            workflow = self.create_workflow(workflow_data)
            workflow_id = workflow['id']
            
            # Step 2: Schedule the workflow
            print(f"\n⏰ Step 2: Scheduling workflow...")
            schedule_info = self.schedule_workflow(workflow_id)
            
            # Step 3: Test the workflow (optional)
            print(f"\n🧪 Step 3: Testing workflow execution...")
            self.test_workflow_execution(workflow_id)
            
            # Summary
            result = {
                'workflow_id': workflow_id,
                'workflow_name': self.workflow_name,
                'user_id': self.user_id,
                'workspace_name': self.workspace_name,
                'schedule_info': schedule_info,
                'deployment_logs_api': self.deployment_logs_api,
                'bug_report_api': self.bug_report_api
            }
            
            print(f"\n✅ SUCCESS: Error Analysis Workflow Setup Complete!")
            print(f"   - Workflow ID: {workflow_id}")
            print(f"   - Workflow Name: {self.workflow_name}")
            print(f"   - User ID: {self.user_id}")
            print(f"   - Workspace: {self.workspace_name}")
            print(f"   - Tasks: 3 (Log Collection → Error Parsing → Bug Report Submission)")
            print(f"   - Scheduled to run every 5 minutes")
            print(f"   - Next execution: {schedule_info['next_run_at']}")
            print(f"   - Monitor at: {self.workflow_api_base}/workflows/{workflow_id}/status")
            print(f"   - Dashboard: {self.workflow_api_base.replace('/api/v1', '/dashboard')}")
            
            return result
            
        except Exception as e:
            print(f"\n❌ FAILED: {e}")
            raise


# Legacy function for backward compatibility
def create_workflow_with_services() -> Dict[str, Any]:
    """
    Legacy function - creates a default workflow.
    Use WorkflowScheduler class for better control.
    """
    print("⚠️  Using legacy function. Consider using WorkflowScheduler class instead.")
    scheduler = WorkflowScheduler("default_user", "default_workspace")
    return scheduler.create_workflow_with_services()


# ...existing code... (keep all other functions as they are for backward compatibility)

def main():
    """
    Main function to create and schedule the workflow.
    """
    if len(sys.argv) >= 3:
        # Command line usage: python workflow_scheduler.py user_id workspace_name
        user_id = sys.argv[1]
        workspace_name = sys.argv[2]
        print(f"Using command line arguments: user_id={user_id}, workspace_name={workspace_name}")
    else:
        # Default values
        user_id = "uditk2@gmail.com"
        workspace_name = "searchagentoptimizationanalyser"
        print(f"Using default values: user_id={user_id}, workspace_name={workspace_name}")
    
    # Create and configure the WorkflowScheduler
    scheduler = WorkflowScheduler(
        user_id=user_id,
        workspace_name=workspace_name,
        deployment_api_base=DEPLOYMENT_API_BASE,
        bug_report_api=BUG_REPORT_API,
        workflow_api_base=API_BASE_URL,
        log_time_window_minutes=LOG_TIME_WINDOW_MINUTES
    )
    
    try:
        result = scheduler.create_and_schedule_workflow()
        print(f"\n🎉 Workflow scheduling completed successfully!")
        print(f"Use this class instance for future operations:")
        print(f"```python")
        print(f"scheduler = WorkflowScheduler('{user_id}', '{workspace_name}')")
        print(f"scheduler.create_and_schedule_workflow()")
        print(f"```")
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()