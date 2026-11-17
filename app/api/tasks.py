from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task
from app.schemas import TaskCreate, TaskResponse, TaskUpdate
from typing import Literal

from app.services.task_service import (
    create_task,
    get_tasks,
    get_task_by_id,
    update_task,
    delete_task,
)

router = APIRouter()


@router.get("", response_model=list[TaskResponse])
def get_tasks_endpoint(
    status_filter: Literal["pending", "in_progress", "completed"] | None = None,
    priority: Literal["low", "medium", "high"] | None = None,
    sort_by: Literal["id", "priority"] = "id",
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return get_tasks(
        db=db,
        status_filter=status_filter,
        priority=priority,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task_endpoint(task: TaskCreate, db: Session = Depends(get_db)):
    return create_task(db, task)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task_endpoint(task_id: int, db: Session = Depends(get_db)):
    task = get_task_by_id(db, task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.put("/{task_id}", response_model=TaskResponse)
def update_task_endpoint(
    task_id: int, task_data: TaskUpdate, db: Session = Depends(get_db)
):
    task = update_task(db, task_id, task_data)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_endpoint(task_id: int, db: Session = Depends(get_db)):
    deleted = delete_task(db, task_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    return None
