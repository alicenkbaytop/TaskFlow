import json

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


def test_tool_action_is_deduplicated_across_fallback_responses(monkeypatch):
    from app.agent import workflow

    calls = []

    class FakeSession:
        def close(self):
            pass

    monkeypatch.setattr(workflow, "SessionLocal", FakeSession)

    def execute_tool(**kwargs):
        calls.append(kwargs)
        return {"id": 7, "title": "Launch plan"}

    monkeypatch.setattr(workflow, "execute_tool", execute_tool)
    args = '{"title":"Launch plan","priority":"high"}'
    first_state = {
        "conversation_id": 1,
        "user_id": "owner-a",
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "primary-call",
                        "function": {"name": "create_task", "arguments": args},
                    }
                ],
            }
        ],
        "answer": "",
        "tool_rounds": 0,
        "executed_tools": {},
    }
    first = workflow.tool_node(first_state)
    fallback_state = {
        **first_state,
        "messages": first["messages"]
        + [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "fallback-call",
                        "function": {"name": "create_task", "arguments": args},
                    }
                ],
            }
        ],
        "executed_tools": first["executed_tools"],
        "tool_rounds": first["tool_rounds"],
    }
    second = workflow.tool_node(fallback_state)
    assert len(calls) == 1
    assert json.loads(second["messages"][-1]["content"]) == {
        "id": 7,
        "title": "Launch plan",
    }
