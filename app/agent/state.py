from typing import Any, TypedDict


class AgentState(TypedDict):
    conversation_id: int
    user_id: str
    messages: list[dict[str, Any]]
    answer: str
    tool_rounds: int
