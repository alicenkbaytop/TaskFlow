from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.schemas import TaskCreate, TaskUpdate
from app.services.task_service import (
    create_task,
    delete_task,
    get_task_by_id,
    get_tasks,
    search_tasks,
    update_task,
)
from app.services.vector_service import search_similar_tasks


def list_tasks_tool(
    db: Session,
    user_id: str,
    status_filter: str | None = None,
    priority: str | None = None,
):
    tasks = get_tasks(
        db=db,
        user_id=user_id,
        status_filter=status_filter,
        priority=priority,
        limit=50,
    )

    return [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "due_date": task.due_date.isoformat() if task.due_date else None,
        }
        for task in tasks
    ]


def search_tasks_tool(db: Session, user_id: str, title: str):

    if not title.strip():
        return {"error": "Search title cannot be empty"}

    tasks = search_tasks(
        db=db,
        user_id=user_id,
        title=title,
    )

    return [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "due_date": task.due_date.isoformat() if task.due_date else None,
        }
        for task in tasks
    ]


def update_task_tool(db: Session, user_id: str, task_id: int, task_data: dict):

    try:
        validated_data = TaskUpdate(**task_data)

    except ValidationError as error:
        return {"error": "Invalid task update arguments", "details": error.errors()}

    task = update_task(
        db=db,
        user_id=user_id,
        task_id=task_id,
        task_data=validated_data,
    )

    if task is None:
        return {"error": f"Task with ID {task_id} not found"}

    return {
        "id": task.id,
        "title": task.title,
        "priority": task.priority,
        "status": task.status,
    }


def create_task_tool(db: Session, user_id: str, task_data: dict):

    try:
        validated_data = TaskCreate(**task_data)

    except ValidationError as error:
        return {"error": "Invalid task creation arguments", "details": error.errors()}

    task = create_task(
        db=db,
        user_id=user_id,
        task_data=validated_data,
    )

    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "status": task.status,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }


def get_task_tool(db: Session, user_id: str, task_id: int):

    task = get_task_by_id(
        db=db,
        user_id=user_id,
        task_id=task_id,
    )

    if task is None:
        return {"error": f"Task with ID {task_id} not found"}

    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }


def complete_task_tool(db: Session, user_id: str, task_id: int):

    task_data = TaskUpdate(status="completed")

    task = update_task(
        db=db,
        user_id=user_id,
        task_id=task_id,
        task_data=task_data,
    )

    if task is None:
        return {"error": f"Task with ID {task_id} not found"}

    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
    }


def delete_task_tool(db: Session, user_id: str, task_id: int):

    deleted = delete_task(
        db=db,
        user_id=user_id,
        task_id=task_id,
    )

    if not deleted:
        return {"error": f"Task with ID {task_id} not found"}

    return {"success": True, "message": f"Task {task_id} was deleted successfully"}


def find_relevant_tasks_tool(db: Session, user_id: str, query: str):
    try:
        # PostgreSQL pgvector searches only this user's embeddings.
        results = search_similar_tasks(db, user_id, query, limit=5)

        current_tasks = []

        for result in results:
            task_id = result["task_id"]

            # PostgreSQL task rows remain the authoritative records.
            task = get_task_by_id(db=db, user_id=user_id, task_id=task_id)

            # Ignore stale vectors for deleted tasks.
            if task is None:
                continue

            current_tasks.append(
                {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "priority": task.priority,
                    "due_date": (task.due_date.isoformat() if task.due_date else None),
                    "score": result["score"],
                }
            )

        return {
            "success": True,
            "results": current_tasks,
            "message": (
                "Relevant tasks found."
                if current_tasks
                else "No sufficiently relevant current tasks found."
            ),
        }

    except Exception:
        return {
            "success": False,
            "error": "Semantic search failed.",
        }
