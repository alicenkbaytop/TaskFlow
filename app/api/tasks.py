from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.rate_limit import limiter
from app.database import get_db
from app.schemas import TaskCreate, TaskResponse, TaskUpdate
from app.services.task_service import (
    create_task,
    delete_task,
    get_task_by_id,
    get_tasks,
    update_task,
)

router = APIRouter()


@router.get("", response_model=list[TaskResponse])
@limiter.limit("120/minute")
def get_tasks_endpoint(
    request: Request,
    user: dict = Depends(get_current_user),
    status_filter: Literal["pending", "in_progress", "completed"] | None = None,
    priority: Literal["low", "medium", "high"] | None = None,
    sort_by: Literal["id", "priority"] = "id",
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return get_tasks(
        db=db,
        user_id=user["id"],
        status_filter=status_filter,
        priority=priority,
        sort_by=sort_by,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("120/minute")
def create_task_endpoint(
    request: Request,
    task: TaskCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return create_task(db, user["id"], task)


@router.get("/{task_id}", response_model=TaskResponse)
@limiter.limit("120/minute")
def get_task_endpoint(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    task = get_task_by_id(db, user["id"], task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.put("/{task_id}", response_model=TaskResponse)
@limiter.limit("120/minute")
def update_task_endpoint(
    request: Request,
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    task = update_task(db, user["id"], task_id, task_data)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("120/minute")
def delete_task_endpoint(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    deleted = delete_task(db, user["id"], task_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
