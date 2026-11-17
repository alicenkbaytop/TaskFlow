def test_get_tasks(client):
    response = client.get("/tasks")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


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
