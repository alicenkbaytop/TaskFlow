from typing import Any, TypedDict


class AgentState(TypedDict):
    conversation_id: int
    messages: list[dict[str, Any]]
    answer: str
    tool_rounds: int
