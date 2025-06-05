import subprocess
import tempfile
import time
import json
import re
import os
from pathlib import Path
from typing import List, Optional

from app.executors import TaskExecutor, ExecutionResult, ExecutorFactory


class DirectExecutor(TaskExecutor):
    """Execute tasks directly in the current Python environment (ideal for Docker)"""
    
    @property
    def name(self) -> str:
        return "direct"
    
    def execute(
        self, 
        script_content: str, 
        requirements: List[str] = None,
        timeout: int = 3600,
        **kwargs
    ) -> ExecutionResult:
        """Execute script directly in current Python environment"""
        start_time = time.time()
        previous_outputs = kwargs.get('previous_outputs', [])
        
        try:
            # Install requirements if provided (but skip common ones already in Docker)
            if requirements:
                common_packages = {'requests', 'urllib3', 'certifi', 'python-dateutil', 'pytz', 'pyyaml', 'pandas', 'numpy', 'openpyxl', 'beautifulsoup4', 'lxml'}
                
                # Filter out packages that are already installed in the Docker image
                packages_to_install = []
                for req in requirements:
                    package_name = req.split('>=')[0].split('==')[0].split('<')[0].split('>')[0].strip()
                    if package_name.lower() not in common_packages:
                        packages_to_install.append(req)
                
                # Install only packages not already in Docker image
                if packages_to_install:
                    for package in packages_to_install:
                        result = subprocess.run(
                            ["pip", "install", package, "--no-cache-dir"],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        if result.returncode != 0:
                            return ExecutionResult(
                                success=False,
                                output=result.stdout,
                                error_message=f"Failed to install {package}: {result.stderr}",
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
                    ["python", script_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=os.environ.copy()
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
            # If pipeline support file doesn't exist, create minimal support
            pipeline_support = """
# Minimal pipeline support
def get_previous_outputs():
    return PREVIOUS_OUTPUTS

def save_task_output(key, value):
    import json
    output = {key: value}
    print(f"__TASK_OUTPUTS_START__{json.dumps(output)}__TASK_OUTPUTS_END__")
"""
        
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
        """No cleanup needed for direct execution"""
        pass


# Register the executor
ExecutorFactory.register_executor("direct", DirectExecutor)