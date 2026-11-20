from sqlalchemy.orm import Session

from app.agent.tools import find_relevant_tasks_tool


def retrieve_task_contexts(db: Session, user_id: str, query: str) -> list[str]:
    # Reuse TaskFlow's existing semantic retrieval.
    result = find_relevant_tasks_tool(
        db=db,
        user_id=user_id,
        query=query,
    )

    if not result["success"]:
        raise RuntimeError(result["error"])

    # Convert retrieved tasks into text contexts for Ragas.
    contexts = []

    for task in result["results"]:
        context = f"Task: {task['title']}\nDescription: {task['description'] or ''}"
        contexts.append(context)

    return contexts
