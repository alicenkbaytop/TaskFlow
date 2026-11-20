import logging

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import Task
from app.services.vector_service import (
    delete_task_vector,
    embedding_provider_configured,
    index_task,
)

logger = logging.getLogger(__name__)


def get_tasks(
    db: Session,
    user_id: str,
    status_filter: str | None = None,
    priority: str | None = None,
    sort_by: str = "id",
    skip: int = 0,
    limit: int = 10,
):
    statement = select(Task).where(Task.user_id == user_id)

    # Filtering
    if status_filter:
        statement = statement.where(Task.status == status_filter)

    if priority:
        statement = statement.where(Task.priority == priority)

    # Sorting
    if sort_by == "id":
        statement = statement.order_by(Task.id.asc())

    elif sort_by == "priority":
        priority_order = case(
            (Task.priority == "high", 1),
            (Task.priority == "medium", 2),
            (Task.priority == "low", 3),
        )
        statement = statement.order_by(priority_order)

    # Pagination
    statement = statement.offset(skip).limit(limit)

    return db.scalars(statement).all()


def get_task_by_id(db: Session, user_id: str, task_id: int):
    return db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user_id))


def create_task(db, user_id: str, task_data):
    new_task = Task(
        user_id=user_id,
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        due_date=task_data.due_date,
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    # Keep the pgvector index synchronized when an embedding provider is set.
    if embedding_provider_configured():
        try:
            index_task(db, user_id, new_task.id, new_task.title, new_task.description)
        except Exception:
            db.rollback()
            logger.exception(
                "Task %s was saved but embedding indexing failed", new_task.id
            )

    return new_task


def update_task(db, user_id: str, task_id, task_data):
    task = get_task_by_id(db, user_id, task_id)

    if task is None:
        return None

    # Remember the original text used for embedding.
    old_text = (task.title, task.description)

    update_data = task_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    # Regenerate embedding only if indexed text changed.
    new_text = (task.title, task.description)

    if old_text != new_text and embedding_provider_configured():
        try:
            index_task(db, user_id, task.id, task.title, task.description)
        except Exception:
            db.rollback()
            logger.exception(
                "Task %s was updated but embedding indexing failed", task.id
            )

    return task


def delete_task(db, user_id: str, task_id):
    task = get_task_by_id(db, user_id, task_id)

    if task is None:
        return False

    db.delete(task)
    db.commit()

    # Remove the associated pgvector row if present.
    delete_task_vector(db, task_id)

    return True


def search_tasks(db: Session, user_id: str, title: str):
    statement = (
        select(Task)
        .where(Task.user_id == user_id, Task.title.ilike(f"%{title.strip()}%"))
        .limit(10)
    )

    return db.scalars(statement).all()
