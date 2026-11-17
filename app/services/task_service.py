from sqlalchemy.orm import Session

from app.models import Task

from sqlalchemy import select, case
from app.services.vector_service import index_task, delete_task_vector

def get_tasks(
    db: Session,
    status_filter: str | None = None,
    priority: str | None = None,
    sort_by: str = "id",
    skip: int = 0,
    limit: int = 10,
):
    statement = select(Task)

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


def get_task_by_id(db: Session, task_id: int):
    return db.get(Task, task_id)


def create_task(db, task_data):
    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        due_date=task_data.due_date,
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    # Index the saved task in Qdrant
    index_task(
        new_task.id,
        new_task.title,
        new_task.description,
    )

    return new_task


def update_task(db, task_id, task_data):
    task = db.get(Task, task_id)

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

    if old_text != new_text:
        index_task(
            task.id,
            task.title,
            task.description,
        )

    return task


def delete_task(db, task_id):
    task = db.get(Task, task_id)

    if task is None:
        return False

    db.delete(task)
    db.commit()

    # Remove its vector from Qdrant
    delete_task_vector(task_id)

    return True


def search_tasks(db: Session, title: str):
    statement = select(Task).where(Task.title.ilike(f"%{title.strip()}%")).limit(10)

    return db.scalars(statement).all()
