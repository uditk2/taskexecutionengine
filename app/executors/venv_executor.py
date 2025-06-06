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
import urllib.request
import sys

from app.executors import TaskExecutor, ExecutionResult, ExecutorFactory
from app.core.config import settings


class VirtualEnvExecutor(TaskExecutor):
    """Execute tasks in isolated virtual environments"""
    
    # Base requirements that match the actual container versions for consistency
    BASE_REQUIREMENTS = [
        "pip==25.1.1",  # Use latest available pip
        "setuptools==65.5.1",
        "wheel",
        "certifi==2025.4.26",
        "urllib3==1.26.20", 
        "cryptography==45.0.3",
        "requests==2.31.0"
    ]
    
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
            
            # Create virtual environment with system site packages to inherit SSL modules
            # This ensures SSL support is properly inherited from the host environment
            venv.create(self.venv_path, with_pip=True, system_site_packages=True)
            
            # Get executable paths
            if os.name == 'nt':  # Windows
                python_exe = self.venv_path / "Scripts" / "python.exe"
                pip_exe = self.venv_path / "Scripts" / "pip.exe"
            else:  # Unix/Linux
                python_exe = self.venv_path / "bin" / "python"
                pip_exe = self.venv_path / "bin" / "pip"
            
            # Verify SSL support is available in the virtual environment
            ssl_available = self._check_ssl_support(python_exe)
            if not ssl_available:
                return ExecutionResult(
                    success=False,
                    output="",
                    error_message="SSL module is not available in the virtual environment. Please rebuild the Docker container.",
                    execution_time=time.time() - start_time
                )
            
            # Upgrade pip to latest version
            pip_upgrade_result = self._install_package_standard(pip_exe, "pip==25.1.1")
            if pip_upgrade_result.returncode != 0:
                print(f"Warning: Failed to upgrade pip: {pip_upgrade_result.stderr}")
            
            # Install base requirements using standard pip (SSL should work now)
            for requirement in self.BASE_REQUIREMENTS:
                if requirement.startswith("pip=="):
                    continue  # Skip pip since we already upgraded it
                result = self._install_package_standard(pip_exe, requirement)
                if result.returncode != 0:
                    print(f"Warning: Failed to install base requirement {requirement}: {result.stderr}")
                    # Continue since system packages might already provide them
            
            # Install user-specified requirements
            if requirements:
                for requirement in requirements:
                    result = self._install_package_standard(pip_exe, requirement)
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
    
    def _check_ssl_support(self, python_exe: Path) -> bool:
        """Check if SSL is available in the Python environment"""
        try:
            result = subprocess.run(
                [str(python_exe), "-c", "import ssl; print('SSL available')"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return "SSL available" in result.stdout and result.returncode == 0
        except Exception:
            return False
    
    def _install_package_standard(self, pip_exe, package, timeout=300):
        """Install a package using standard pip installation"""
        try:
            cmd = [str(pip_exe), "install", "--no-cache-dir", "--disable-pip-version-check", package]
            print(f"Installing {package} using standard pip installation...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                print(f"✅ Successfully installed {package}")
            else:
                print(f"❌ Failed to install {package}: {result.stderr}")
            
            return result
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout expired installing {package}")
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="Timeout expired")
        except Exception as e:
            print(f"⚠️ Unexpected error installing {package}: {e}")
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr=str(e))
    
    def cleanup(self) -> None:
        """Clean up virtual environment"""
        if self.venv_path and self.venv_path.exists():
            shutil.rmtree(self.venv_path, ignore_errors=True)
            self.venv_path = None


# Register the executor
ExecutorFactory.register_executor("virtualenv", VirtualEnvExecutor)
