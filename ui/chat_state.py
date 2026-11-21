"""Small helpers for the Streamlit conversation display state."""


def initialize_chat_state(state, query_params=None) -> None:
    """Initialize transient UI state and restore an active ID from the URL."""
    defaults = {
        "active_conversation_id": None,
        "chat_history": [],
        "loaded_conversation_id": None,
        "conversation_picker": None,
        "chat_request_in_flight": False,
    }
    for key, value in defaults.items():
        if key not in state:
            state[key] = value

    if state.get("active_conversation_id") is None and query_params is not None:
        raw_id = query_params.get("conversation_id")
        try:
            state["active_conversation_id"] = int(raw_id) if raw_id else None
        except (TypeError, ValueError):
            state["active_conversation_id"] = None

    apply_pending_conversation_selection(state)


def apply_pending_conversation_selection(state) -> None:
    """Apply widget-key changes before the conversation picker is rendered."""
    if "pending_conversation_id" in state:
        state["conversation_picker"] = state.pop("pending_conversation_id")


def schedule_conversation_selection(state, conversation_id: int | None) -> None:
    """Defer selection changes until before the next picker instantiation."""
    state["pending_conversation_id"] = conversation_id


def clear_chat_state(state) -> None:
    """Clear the transient transcript and active conversation selection."""
    state["active_conversation_id"] = None
    state["chat_history"] = []
    state["loaded_conversation_id"] = None
    schedule_conversation_selection(state, None)
    state["chat_request_in_flight"] = False


def mark_conversation_deleted(state, query_params) -> None:
    """Clear local selection only after the API confirms deletion."""
    clear_chat_state(state)
    query_params.pop("conversation_id", None)
