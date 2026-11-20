from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.tools import get_task_tool, list_tasks_tool
from app.models import Base
from app.services.llm_service import execute_tool


def test_tool_call_uses_authenticated_owner_and_shared_task_service():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        result = execute_tool(
            db=db,
            user_id="owner-a",
            tool_name="create_task",
            arguments={"title": "Private AI task"},
        )
        task_id = result["id"]

        assert list_tasks_tool(db, "owner-a")[0]["id"] == task_id
        assert list_tasks_tool(db, "owner-b") == []
        assert get_task_tool(db, "owner-b", task_id)["error"]
    engine.dispose()


def test_model_cannot_supply_an_owner_id():
    result = execute_tool(
        db=None,
        user_id="verified-owner",
        tool_name="create_task",
        arguments={"title": "Forged task", "user_id": "victim"},
    )
    assert result["error"] == "Invalid tool arguments"
