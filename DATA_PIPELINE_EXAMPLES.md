# Data Pipeline Example for Task Execution Engine

This example demonstrates how to create a data pipeline where Task 2 can use the output of Task 1.

## Data Pipeline Features

### 1. Setting Task Outputs
Tasks can set structured outputs that subsequent tasks can access:

```python
# In Task 1
set_task_output('user_count', 100)
set_task_output('data_file', 'processed_data.csv')
set_task_output('metadata', {'version': '1.0', 'processed_at': '2025-06-04'})
```

### 2. Getting Previous Task Outputs
Subsequent tasks can access outputs from previous tasks:

```python
# In Task 2 - Get outputs by task name
task1_outputs = get_task_output(task_name='Data Processing')
user_count = task1_outputs.get('user_count', 0)

# Or get outputs by task order (0-based)
task1_outputs = get_task_output(task_order=0)
```

### 3. Available Helper Functions

- `get_task_output(task_name=None, task_order=None)` - Get outputs from a previous task
- `set_task_output(key, value)` - Set output that can be used by subsequent tasks
- `save_task_outputs()` - Manually save outputs (automatically called at script end)

## Example Data Pipeline Workflow

### Task 1: Data Generator (Order: 0)
```python
import random
import json

# Generate some sample data
data = []
for i in range(10):
    data.append({
        'id': i,
        'value': random.randint(1, 100),
        'category': random.choice(['A', 'B', 'C'])
    })

# Calculate statistics
total_count = len(data)
average_value = sum(item['value'] for item in data) / total_count
max_value = max(item['value'] for item in data)

print(f"Generated {total_count} data points")
print(f"Average value: {average_value:.2f}")
print(f"Max value: {max_value}")

# Set outputs for next tasks
set_task_output('data', data)
set_task_output('statistics', {
    'count': total_count,
    'average': average_value,
    'max': max_value
})
set_task_output('summary', f"Processed {total_count} items with avg {average_value:.2f}")
```

### Task 2: Data Processor (Order: 1)
```python
# Get data from previous task
task1_outputs = get_task_output(task_order=0)
data = task1_outputs.get('data', [])
stats = task1_outputs.get('statistics', {})

print(f"Received {len(data)} items from Task 1")
print(f"Previous stats: {stats}")

# Process the data
filtered_data = [item for item in data if item['value'] > stats.get('average', 0)]
categories = {}
for item in filtered_data:
    cat = item['category']
    categories[cat] = categories.get(cat, 0) + 1

print(f"Filtered to {len(filtered_data)} items above average")
print(f"Category distribution: {categories}")

# Set outputs for next task
set_task_output('filtered_data', filtered_data)
set_task_output('category_counts', categories)
set_task_output('filter_summary', f"Kept {len(filtered_data)} of {len(data)} items")
```

### Task 3: Report Generator (Order: 2)
```python
# Get outputs from all previous tasks
task1_outputs = get_task_output(task_order=0)
task2_outputs = get_task_output(task_order=1)

# Or get by name
# task1_outputs = get_task_output(task_name='Data Generator')
# task2_outputs = get_task_output(task_name='Data Processor')

original_stats = task1_outputs.get('statistics', {})
filtered_data = task2_outputs.get('filtered_data', [])
categories = task2_outputs.get('category_counts', {})

# Generate final report
report = {
    'pipeline_summary': {
        'original_count': original_stats.get('count', 0),
        'filtered_count': len(filtered_data),
        'retention_rate': len(filtered_data) / original_stats.get('count', 1) * 100
    },
    'category_analysis': categories,
    'recommendations': []
}

# Add recommendations based on data
if report['pipeline_summary']['retention_rate'] > 50:
    report['recommendations'].append('High retention rate - good data quality')
else:
    report['recommendations'].append('Low retention rate - review filtering criteria')

if 'A' in categories and categories['A'] > len(filtered_data) * 0.5:
    report['recommendations'].append('Category A dominates - consider separate analysis')

print("=== FINAL REPORT ===")
print(f"Processed {original_stats.get('count', 0)} → {len(filtered_data)} items")
print(f"Retention rate: {report['pipeline_summary']['retention_rate']:.1f}%")
print(f"Categories: {categories}")
print(f"Recommendations: {report['recommendations']}")

# Set final outputs
set_task_output('final_report', report)
set_task_output('success', True)
```

## Tips for Building Data Pipelines

1. **Use meaningful output keys**: Choose descriptive names for your outputs
2. **Handle missing data**: Always provide defaults when getting outputs
3. **Validate inputs**: Check that previous task outputs contain expected data
4. **Keep outputs serializable**: Use JSON-compatible data types (dict, list, str, int, float, bool)
5. **Document your pipeline**: Use clear task names and descriptions