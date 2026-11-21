def test_get_tasks(client):
    response = client.get("/tasks")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_task(client):
    response = client.post(
        "/tasks",
        json={
            "title": "Learn Pytest",
            "description": "Write my first API test",
            "priority": "high",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "Learn Pytest"
    assert data["priority"] == "high"
    assert data["status"] == "pending"
    assert "id" in data


def test_create_task_invalid_priority(client):
    response = client.post(
        "/tasks", json={"title": "Invalid task", "priority": "urgent"}
    )

    assert response.status_code == 422


def test_get_task_by_id(client):
    create_response = client.post("/tasks", json={"title": "Test GET"})

    task_id = create_response.json()["id"]

    response = client.get(f"/tasks/{task_id}")

    assert response.status_code == 200
    assert response.json()["title"] == "Test GET"


def test_sort_tasks_by_priority(client):
    client.post("/tasks", json={"title": "Low priority", "priority": "low"})

    client.post("/tasks", json={"title": "High priority", "priority": "high"})

    client.post("/tasks", json={"title": "Medium priority", "priority": "medium"})

    response = client.get("/tasks?sort_by=priority")

    assert response.status_code == 200

    tasks = response.json()

    priorities = [task["priority"] for task in tasks]

    assert priorities == ["high", "medium", "low"]


def test_update_task(client):
    create_response = client.post("/tasks", json={"title": "Original title"})

    task_id = create_response.json()["id"]

    response = client.put(
        f"/tasks/{task_id}",
        json={
            "title": "Updated title",
            "description": "Updated description",
            "priority": "high",
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated title"
    assert response.json()["priority"] == "high"


def test_delete_task(client):
    create_response = client.post("/tasks", json={"title": "Task to delete"})

    task_id = create_response.json()["id"]

    delete_response = client.delete(f"/tasks/{task_id}")

    assert delete_response.status_code == 204

    get_response = client.get(f"/tasks/{task_id}")

    assert get_response.status_code == 404


def test_task_isolation_by_authenticated_user(client):
    created = client.post("/tasks", json={"title": "Private task"})
    task_id = created.json()["id"]
    from app.core.auth import get_current_user
    from main import app

    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-b"}
    try:
        assert client.get(f"/tasks/{task_id}").status_code == 404
        assert client.get("/tasks").json() == []
        assert (
            client.put(f"/tasks/{task_id}", json={"title": "stolen"}).status_code == 404
        )
        assert client.delete(f"/tasks/{task_id}").status_code == 404
    finally:
        app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-a"}


def test_chat_conversations_are_user_scoped(client, monkeypatch):
    from app.api import chat as chat_api
    from app.core.auth import get_current_user
    from main import app

    monkeypatch.setattr(chat_api, "ask_gemini", lambda *args: "Hello")
    created = client.post("/chat/", json={"message": "Hello"})
    assert created.status_code == 200
    conversation_id = created.json()["conversation_id"]
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-b"}
    try:
        assert client.get("/chat/conversations").json() == []
        assert client.get(f"/chat/conversations/{conversation_id}").status_code == 404
        assert (
            client.post(
                "/chat/", json={"message": "Hello", "conversation_id": conversation_id}
            ).status_code
            == 404
        )
    finally:
        app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-a"}


def test_conversation_can_be_renamed_and_deleted(client, monkeypatch):
    from app.api import chat as chat_api

    monkeypatch.setattr(chat_api, "ask_gemini", lambda *args: "Hello")
    created = client.post("/chat/conversations")
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    detail = client.get(f"/chat/conversations/{conversation_id}").json()
    assert detail["title"] == "New conversation"
    assert [message["role"] for message in detail["messages"]] == []

    renamed = client.patch(
        f"/chat/conversations/{conversation_id}", json={"title": "Planning"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Planning"
    assert client.delete(f"/chat/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/chat/conversations/{conversation_id}").status_code == 404
    assert client.get("/chat/conversations").json() == []


def test_conversation_delete_preserves_ownership(client):
    from app.core.auth import get_current_user
    from main import app

    created = client.post("/chat/conversations")
    conversation_id = created.json()["id"]
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-b"}
    try:
        assert (
            client.delete(f"/chat/conversations/{conversation_id}").status_code == 404
        )
    finally:
        app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-a"}
    assert client.get(f"/chat/conversations/{conversation_id}").status_code == 200


def test_chat_persists_exchange_only_after_success(client, monkeypatch):
    from app.agent import workflow

    monkeypatch.setattr(workflow, "run_agent", lambda **kwargs: "Your tasks are ready.")
    response = client.post("/chat/", json={"message": "What are my tasks?"})
    assert response.status_code == 200
    conversation_id = response.json()["conversation_id"]
    detail = client.get(f"/chat/conversations/{conversation_id}").json()
    assert [message["role"] for message in detail["messages"]] == [
        "user",
        "assistant",
    ]
    assert detail["messages"][0]["content"] == "What are my tasks?"
    assert detail["messages"][1]["content"] == "Your tasks are ready."
    assert detail["messages"][0]["created_at"] <= detail["messages"][1]["created_at"]


def test_failed_new_chat_leaves_no_orphan_conversation(client, monkeypatch):
    from app.agent import workflow

    def fail(**kwargs):
        raise workflow.AIWorkflowError("The AI provider timed out.")

    monkeypatch.setattr(workflow, "run_agent", fail)
    response = client.post("/chat/", json={"message": "Hello"})
    assert response.status_code == 503
    assert client.get("/chat/conversations").json() == []


def test_deleting_conversation_removes_persisted_messages(client, monkeypatch):
    from app.agent import workflow

    monkeypatch.setattr(workflow, "run_agent", lambda **kwargs: "Persisted answer")
    response = client.post("/chat/", json={"message": "Persist this exchange"})
    conversation_id = response.json()["conversation_id"]
    assert (
        len(client.get(f"/chat/conversations/{conversation_id}").json()["messages"])
        == 2
    )

    deleted = client.delete(f"/chat/conversations/{conversation_id}")

    assert deleted.status_code == 204
    assert client.get(f"/chat/conversations/{conversation_id}").status_code == 404


def test_protected_api_requires_authentication(client):
    from app.core.auth import get_current_user
    from main import app

    app.dependency_overrides.pop(get_current_user)
    try:
        assert client.get("/tasks").status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-a"}
