from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    """Result of task execution"""
    success: bool
    output: str
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    exit_code: Optional[int] = None


class TaskExecutor(ABC):
    """Abstract base class for task executors"""
    
    @abstractmethod
    def execute(
        self, 
        script_content: str, 
        requirements: List[str] = None,
        timeout: int = 3600,
        **kwargs
    ) -> ExecutionResult:
        """
        Execute a task script with given requirements
        
        Args:
            script_content: Python script to execute
            requirements: List of pip packages to install
            timeout: Maximum execution time in seconds
            **kwargs: Additional executor-specific parameters
        
        Returns:
            ExecutionResult with execution details
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up any resources created during execution"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this executor"""
        pass


class ExecutorFactory:
    """Factory for creating task executors"""
    
    _executors = {}
    
    @classmethod
    def register_executor(cls, name: str, executor_class: type):
        """Register an executor class"""
        cls._executors[name] = executor_class
    
    @classmethod
    def create_executor(cls, name: str, **kwargs) -> TaskExecutor:
        """Create an executor instance by name"""
        if name not in cls._executors:
            raise ValueError(f"Unknown executor: {name}")
        return cls._executors[name](**kwargs)
    
    @classmethod
    def list_executors(cls) -> List[str]:
        """List available executor names"""
        return list(cls._executors.keys())
