import os
import subprocess
import tempfile
import shutil
import venv
import time
from pathlib import Path
from typing import List, Optional

from app.executors import TaskExecutor, ExecutionResult, ExecutorFactory
from app.core.config import settings


class VirtualEnvExecutor(TaskExecutor):
    """Execute tasks in isolated virtual environments"""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or settings.VENV_BASE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.venv_path = None
    
    @property
    def name(self) -> str:
        return "virtualenv"
    
    def execute(
        self, 
        script_content: str, 
        requirements: List[str] = None,
        timeout: int = 3600,
        **kwargs
    ) -> ExecutionResult:
        """Execute script in isolated virtual environment"""
        start_time = time.time()
        
        try:
            # Create unique virtual environment
            timestamp = str(int(time.time() * 1000))
            self.venv_path = self.base_path / f"venv_{timestamp}"
            
            # Create virtual environment
            venv.create(self.venv_path, with_pip=True)
            
            # Get executable paths
            if os.name == 'nt':  # Windows
                python_exe = self.venv_path / "Scripts" / "python.exe"
                pip_exe = self.venv_path / "Scripts" / "pip.exe"
            else:  # Unix/Linux
                python_exe = self.venv_path / "bin" / "python"
                pip_exe = self.venv_path / "bin" / "pip"
            
            # Install requirements
            if requirements:
                for requirement in requirements:
                    result = subprocess.run(
                        [str(pip_exe), "install", requirement],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    if result.returncode != 0:
                        return ExecutionResult(
                            success=False,
                            output="",
                            error_message=f"Failed to install {requirement}: {result.stderr}",
                            execution_time=time.time() - start_time
                        )
            
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
                script_file.write(script_content)
                script_path = script_file.name
            
            try:
                # Execute the script
                result = subprocess.run(
                    [str(python_exe), script_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.venv_path)
                )
                
                execution_time = time.time() - start_time
                
                if result.returncode == 0:
                    return ExecutionResult(
                        success=True,
                        output=result.stdout,
                        execution_time=execution_time,
                        exit_code=result.returncode
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        output=result.stdout,
                        error_message=result.stderr,
                        execution_time=execution_time,
                        exit_code=result.returncode
                    )
            finally:
                os.unlink(script_path)
                
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="",
                error_message=f"Task execution timed out after {timeout} seconds",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error_message=f"Execution failed: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def cleanup(self) -> None:
        """Clean up virtual environment"""
        if self.venv_path and self.venv_path.exists():
            shutil.rmtree(self.venv_path, ignore_errors=True)
            self.venv_path = None


# Register the executor
ExecutorFactory.register_executor("virtualenv", VirtualEnvExecutor)
