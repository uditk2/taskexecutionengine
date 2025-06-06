from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models.workflow import Workflow, WorkflowStatus
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific task by ID"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_orm(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int, 
    task_update: TaskUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update a specific task"""
    # Get the task
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Verify workflow exists and check if it's running
    workflow_result = await db.execute(select(Workflow).where(Workflow.id == task.workflow_id))
    workflow = workflow_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Associated workflow not found")
    
    # Check if workflow is running
    if workflow.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot edit tasks in a running workflow")
    
    # Update task fields
    for field, value in task_update.dict(exclude_unset=True).items():
        if field != "status":  # Don't allow status updates through edit
            setattr(task, field, value)
    
    await db.commit()
    await db.refresh(task)
    return TaskResponse.from_orm(task)


@router.delete("/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a task"""
    # Get the task
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Verify workflow exists and check if it's running
    workflow_result = await db.execute(select(Workflow).where(Workflow.id == task.workflow_id))
    workflow = workflow_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Associated workflow not found")
    
    # Check if workflow is running
    if workflow.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete tasks from a running workflow")
    
    await db.delete(task)
    await db.commit()
    return {"message": "Task deleted successfully"}


# Workflow-specific task endpoints
@router.get("/workflow/{workflow_id}", response_model=List[TaskResponse])
async def get_workflow_tasks(
    workflow_id: int, 
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """Get all tasks for a specific workflow"""
    # Verify workflow exists
    workflow_result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = workflow_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Get tasks
    result = await db.execute(
        select(Task)
        .where(Task.workflow_id == workflow_id)
        .order_by(Task.order, Task.id)
        .offset(skip)
        .limit(limit)
    )
    tasks = result.scalars().all()
    return [TaskResponse.from_orm(task) for task in tasks]


@router.post("/workflow/{workflow_id}", response_model=TaskResponse)
async def add_task_to_workflow(
    workflow_id: int, 
    task_data: TaskCreate, 
    db: AsyncSession = Depends(get_db)
):
    """Add a new task to an existing workflow"""
    # Verify workflow exists
    workflow_result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = workflow_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if workflow is running
    if workflow.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot add tasks to a running workflow")
    
    # If no order specified, put it at the end
    if task_data.order is None:
        max_order_result = await db.execute(
            select(Task.order).where(Task.workflow_id == workflow_id).order_by(Task.order.desc()).limit(1)
        )
        max_order = max_order_result.scalar_one_or_none()
        task_data.order = (max_order or 0) + 1
    
    # Create new task
    task = Task(
        workflow_id=workflow_id,
        name=task_data.name,
        description=task_data.description,
        script_content=task_data.script_content,
        requirements=task_data.requirements,
        order=task_data.order
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return TaskResponse.from_orm(task)


@router.get("/workflow/{workflow_id}/task/{task_id}", response_model=TaskResponse)
async def get_workflow_task(workflow_id: int, task_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific task within a workflow"""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.workflow_id == workflow_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found in this workflow")
    return TaskResponse.from_orm(task)


@router.put("/workflow/{workflow_id}/task/{task_id}", response_model=TaskResponse)
async def update_workflow_task(
    workflow_id: int, 
    task_id: int, 
    task_update: TaskUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update a specific task within a workflow"""
    # Verify workflow exists
    workflow_result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = workflow_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if workflow is running
    if workflow.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot edit tasks in a running workflow")
    
    # Get the task
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.workflow_id == workflow_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found in this workflow")
    
    # Update task fields
    for field, value in task_update.dict(exclude_unset=True).items():
        if field != "status":  # Don't allow status updates through edit
            setattr(task, field, value)
    
    await db.commit()
    await db.refresh(task)
    return TaskResponse.from_orm(task)


@router.delete("/workflow/{workflow_id}/task/{task_id}")
async def delete_workflow_task(
    workflow_id: int, 
    task_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """Delete a task from a workflow"""
    # Verify workflow exists
    workflow_result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = workflow_result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Check if workflow is running
    if workflow.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete tasks from a running workflow")
    
    # Get the task
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.workflow_id == workflow_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found in this workflow")
    
    await db.delete(task)
    await db.commit()
    return {"message": "Task deleted successfully"}