import tempfile
import time
import uuid
import json
import re
from pathlib import Path
from typing import List, Optional

from app.executors import TaskExecutor, ExecutionResult, ExecutorFactory
from app.core.config import settings

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


class DockerExecutor(TaskExecutor):
    """Execute tasks in isolated Docker containers"""
    
    def __init__(self, image: str = None):
        if not DOCKER_AVAILABLE:
            raise ImportError("Docker library not available. Install with: pip install docker")
        
        self.image = image or settings.DOCKER_IMAGE
        self.client = None
        self.container = None
        
        try:
            self.client = docker.from_env()
            # Test Docker connection
            self.client.ping()
        except Exception as e:
            raise RuntimeError(f"Cannot connect to Docker daemon: {e}")
    
    @property
    def name(self) -> str:
        return "docker"
    
    def execute(
        self, 
        script_content: str, 
        requirements: List[str] = None,
        timeout: int = 3600,
        **kwargs
    ) -> ExecutionResult:
        """Execute script in isolated Docker container"""
        start_time = time.time()
        previous_outputs = kwargs.get('previous_outputs', [])
        
        try:
            # Create unique container name
            container_name = f"task_executor_{uuid.uuid4().hex[:8]}"
            
            # Prepare enhanced script with data pipeline support
            enhanced_script = self._prepare_script_with_pipeline_support(script_content, previous_outputs)
            
            # Create a shell script that properly handles task outputs
            shell_script = """#!/bin/sh
# Function to log messages
log() {
    echo "[EXECUTOR] $1"
}

log "Starting task execution..."

# Create a temporary file for the script and its output
OUTPUT_FILE=$(mktemp)

# Write the Python script
cat << 'EOF' > /tmp/script.py
%s
EOF

# Install requirements if provided
%s

# Execute the Python script and capture output
log "Executing Python script..."
python /tmp/script.py | tee $OUTPUT_FILE
SCRIPT_EXIT=$?

log "Script execution completed with exit code $SCRIPT_EXIT"

# Check if we have task outputs in the output file
if grep -q "__TASK_OUTPUTS_START__" $OUTPUT_FILE; then
    log "Task outputs detected, marking task as successful"
    exit 0
else
    log "No task outputs found, using script exit code: $SCRIPT_EXIT"
    exit $SCRIPT_EXIT
fi
""" % (
    enhanced_script,
    'log "Installing requirements..."; pip install ' + ' '.join(requirements) + ' || log "Warning: Some requirements may have failed to install"' if requirements else '# No requirements to install'
)
            
            # Run container with the shell script
            self.container = self.client.containers.run(
                self.image,
                command=["sh", "-c", shell_script],
                name=container_name,
                detach=True,
                remove=False,
                mem_limit="512m",
                cpu_quota=50000,
                environment={"PYTHONUNBUFFERED": "1"}  # Ensure immediate output
            )
            
            # Wait for completion
            try:
                result = self.container.wait(timeout=timeout)
                logs = self.container.logs(stdout=True, stderr=True).decode('utf-8')
                
                execution_time = time.time() - start_time
                exit_code = result['StatusCode']
                
                # Extract task outputs from logs
                task_outputs = self._extract_task_outputs(logs)
                
                # If we have task outputs, consider the task successful regardless of exit code
                if task_outputs:
                    return ExecutionResult(
                        success=True,
                        output=logs,
                        execution_time=execution_time,
                        exit_code=0,  # Override to success when we have task outputs
                        task_outputs=task_outputs
                    )
                elif exit_code == 0:
                    return ExecutionResult(
                        success=True,
                        output=logs,
                        execution_time=execution_time,
                        exit_code=exit_code,
                        task_outputs={}
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        output=logs,
                        error_message=f"Container exited with code {exit_code}",
                        execution_time=execution_time,
                        exit_code=exit_code,
                        task_outputs=task_outputs
                    )
            except Exception as e:
                try:
                    logs = self.container.logs(stdout=True, stderr=True).decode('utf-8')
                    # Try to extract task outputs even in case of exception
                    task_outputs = self._extract_task_outputs(logs)
                    
                    # If we have task outputs, consider it successful
                    if task_outputs:
                        return ExecutionResult(
                            success=True,
                            output=logs,
                            execution_time=time.time() - start_time,
                            exit_code=0,  # Override to success
                            task_outputs=task_outputs
                        )
                except Exception:
                    logs = ""
                
                return ExecutionResult(
                    success=False,
                    output=logs,
                    error_message=f"Container execution failed: {str(e)}",
                    execution_time=time.time() - start_time
                )
                
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error_message=f"Failed to start container: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _prepare_script_with_pipeline_support(self, script_content: str, previous_outputs: List[dict]) -> str:
        """Prepare script with data pipeline support"""
        # Read the pipeline support script
        pipeline_script_path = Path(__file__).parent / "pipeline_support.py"
        
        try:
            with open(pipeline_script_path, 'r') as f:
                pipeline_support = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Pipeline support script not found at {pipeline_script_path}")
        
        # Inject the previous outputs data
        pipeline_setup = f"""# === Data Pipeline Support ===
{pipeline_support}

# Inject previous task outputs
PREVIOUS_OUTPUTS = {json.dumps(previous_outputs)}

# === User Script ===
"""
        
        return pipeline_setup + script_content
    
    def _extract_task_outputs(self, stdout: str) -> dict:
        """Extract structured task outputs from stdout"""
        try:
            # Look for the special output markers
            pattern = r'__TASK_OUTPUTS_START__(.+?)__TASK_OUTPUTS_END__'
            matches = re.findall(pattern, stdout, re.DOTALL)
            
            if matches:
                # Get the last output (in case multiple calls)
                return json.loads(matches[-1])
            
            return {}
        except (json.JSONDecodeError, IndexError):
            return {}
    
    def cleanup(self) -> None:
        """Clean up Docker container"""
        if self.container:
            try:
                self.container.stop(timeout=10)
                self.container.remove()
            except Exception:
                pass
            finally:
                self.container = None


# Register the executor only if Docker is available
if DOCKER_AVAILABLE:
    ExecutorFactory.register_executor("docker", DockerExecutor)
