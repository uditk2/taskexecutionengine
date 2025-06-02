import tempfile
import time
import uuid
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
        
        try:
            # Create unique container name
            container_name = f"task_executor_{uuid.uuid4().hex[:8]}"
            
            # Prepare script and requirements
            script_commands = []
            
            # Install requirements if provided
            if requirements:
                pip_install = "pip install " + " ".join(requirements)
                script_commands.append(pip_install)
            
            # Add the actual script
            script_commands.append(f"cat << 'EOF' > /tmp/script.py\n{script_content}\nEOF")
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
                
                if exit_code == 0:
                    return ExecutionResult(
                        success=True,
                        output=logs,
                        execution_time=execution_time,
                        exit_code=exit_code
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        output=logs,
                        error_message=f"Container exited with code {exit_code}",
                        execution_time=execution_time,
                        exit_code=exit_code
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
