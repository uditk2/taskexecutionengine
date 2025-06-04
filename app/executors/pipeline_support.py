"""
Data Pipeline Support Script for Task Execution Engine
This script is injected into every task to provide data pipeline functionality.
"""

import json
import sys

# Data pipeline support - previous task outputs will be injected here
PREVIOUS_OUTPUTS = []

def get_task_output(task_name=None, task_order=None):
    """Get output from a previous task by name or order"""
    for output in PREVIOUS_OUTPUTS:
        if task_name and output.get('task_name') == task_name:
            return output.get('outputs', {})
        if task_order is not None and output.get('task_order') == task_order:
            return output.get('outputs', {})
    return {}

# Helper function to set outputs for next tasks
TASK_OUTPUTS = {}

def set_task_output(key, value):
    """Set output that can be used by subsequent tasks"""
    TASK_OUTPUTS[key] = value

def save_task_outputs():
    """Save task outputs for pipeline"""
    if TASK_OUTPUTS:
        print(f"__TASK_OUTPUTS_START__{json.dumps(TASK_OUTPUTS)}__TASK_OUTPUTS_END__")

# Auto-save outputs at script end
import atexit
atexit.register(save_task_outputs)