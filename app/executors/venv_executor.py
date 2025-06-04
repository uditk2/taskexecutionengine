import os
import subprocess
import tempfile
import shutil
import venv
import time
import json
import re
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
        previous_outputs = kwargs.get('previous_outputs', [])
        
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
            
            # Prepare enhanced script with data pipeline support
            enhanced_script = self._prepare_script_with_pipeline_support(script_content, previous_outputs)
            
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as script_file:
                script_file.write(enhanced_script)
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
                
                # Extract task outputs from script output
                task_outputs = self._extract_task_outputs(result.stdout)
                
                if result.returncode == 0:
                    return ExecutionResult(
                        success=True,
                        output=result.stdout,
                        execution_time=execution_time,
                        exit_code=result.returncode,
                        task_outputs=task_outputs
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        output=result.stdout,
                        error_message=result.stderr,
                        execution_time=execution_time,
                        exit_code=result.returncode,
                        task_outputs=task_outputs
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
        """Clean up virtual environment"""
        if self.venv_path and self.venv_path.exists():
            shutil.rmtree(self.venv_path, ignore_errors=True)
            self.venv_path = None


# Register the executor
ExecutorFactory.register_executor("virtualenv", VirtualEnvExecutor)
