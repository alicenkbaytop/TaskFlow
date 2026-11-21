from typing import Any, TypedDict


class AgentState(TypedDict):
    conversation_id: int
    user_id: str
    messages: list[dict[str, Any]]
    answer: str
    tool_rounds: int
    failed: bool
    error_message: str
    active_provider: str | None
    executed_tools: dict[str, Any]
