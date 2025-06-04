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
            
            # Prepare script and requirements
            script_commands = []
            
            # Install requirements if provided
            if requirements:
                pip_install = "pip install " + " ".join(requirements)
                script_commands.append(pip_install)
            
            # Add the enhanced script
            script_commands.append(f"cat << 'EOF' > /tmp/script.py\n{enhanced_script}\nEOF")
            script_commands.append("python /tmp/script.py")
            
            # Combine all commands
            full_command = " && ".join(script_commands)
            
            # Run container
            self.container = self.client.containers.run(
                self.image,
                command=["sh", "-c", full_command],
                name=container_name,
                detach=True,
                remove=False,
                mem_limit="512m",
                cpu_quota=50000,
                network_mode="none"
            )
            
            # Wait for completion
            try:
                result = self.container.wait(timeout=timeout)
                logs = self.container.logs(stdout=True, stderr=True).decode('utf-8')
                
                execution_time = time.time() - start_time
                exit_code = result['StatusCode']
                
                # Extract task outputs from logs
                task_outputs = self._extract_task_outputs(logs)
                
                if exit_code == 0:
                    return ExecutionResult(
                        success=True,
                        output=logs,
                        execution_time=execution_time,
                        exit_code=exit_code,
                        task_outputs=task_outputs
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
