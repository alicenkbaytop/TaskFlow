from ui.chat_state import (
    initialize_chat_state,
    mark_conversation_deleted,
    schedule_conversation_selection,
)


def test_chat_state_initializes_all_values_without_session_defaults():
    state = {}

    initialize_chat_state(state)

    assert state == {
        "active_conversation_id": None,
        "chat_history": [],
        "loaded_conversation_id": None,
        "conversation_picker": None,
        "chat_request_in_flight": False,
    }


def test_chat_state_restores_active_conversation_from_url():
    state = {}

    initialize_chat_state(state, {"conversation_id": "42"})

    assert state["active_conversation_id"] == 42
    assert state["chat_history"] == []


def test_pending_conversation_selection_applies_before_next_widget_run():
    state = {}
    initialize_chat_state(state)

    schedule_conversation_selection(state, 42)

    assert state["conversation_picker"] is None
    assert state["pending_conversation_id"] == 42

    initialize_chat_state(state)

    assert state["conversation_picker"] == 42
    assert "pending_conversation_id" not in state


def test_pending_empty_selection_resets_picker_before_next_widget_run():
    state = {"conversation_picker": 42}

    schedule_conversation_selection(state, None)
    assert state["conversation_picker"] == 42

    initialize_chat_state(state)

    assert state["conversation_picker"] is None
    assert "pending_conversation_id" not in state


def test_invalid_conversation_url_does_not_break_initialization():
    state = {}

    initialize_chat_state(state, {"conversation_id": "not-an-id"})

    assert state["active_conversation_id"] is None


def test_confirmed_delete_clears_active_ui_state_and_url():
    state = {
        "active_conversation_id": 42,
        "chat_history": [{"role": "user", "content": "hello"}],
        "loaded_conversation_id": 42,
        "conversation_picker": 42,
        "chat_request_in_flight": False,
    }
    query_params = {"conversation_id": "42", "other": "preserve"}

    mark_conversation_deleted(state, query_params)

    assert state["active_conversation_id"] is None
    assert state["chat_history"] == []
    assert state["loaded_conversation_id"] is None
    assert state["conversation_picker"] == 42
    assert state["pending_conversation_id"] is None
    assert "conversation_id" not in query_params
    assert query_params["other"] == "preserve"

    initialize_chat_state(state)
    assert state["conversation_picker"] is None
