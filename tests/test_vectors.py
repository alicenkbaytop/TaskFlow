from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models import Base, Task, TaskEmbedding
from app.services import vector_service


def test_embedding_sync_and_removal_without_live_gemini(monkeypatch):
    monkeypatch.setattr(vector_service, "create_embedding", lambda text: [0.1] * 768)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        task = Task(user_id="user-a", title="Plan launch")
        db.add(task)
        db.commit()
        vector_service.index_task(db, "user-a", task.id, task.title, None)
        row = db.get(TaskEmbedding, task.id)
        assert row.user_id == "user-a"
        assert len(row.embedding) == 768
        assert "Plan launch" in row.content

        vector_service.index_task(db, "user-a", task.id, "Plan release", "QA")
        assert "Plan release" in db.get(TaskEmbedding, task.id).content
        vector_service.delete_task_vector(db, task.id)
        assert db.get(TaskEmbedding, task.id) is None
    engine.dispose()


def test_semantic_search_requires_postgresql():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db, pytest.raises(RuntimeError, match="PostgreSQL"):
        vector_service.search_similar_tasks(db, "user-a", "launch date")
    engine.dispose()


def test_semantic_query_scopes_by_owner(monkeypatch):
    monkeypatch.setattr(vector_service, "create_embedding", lambda text: [0.1] * 768)
    embedding = TaskEmbedding(
        task_id=9, user_id="user-a", content="task", embedding=[0.1] * 768
    )
    captured = {}

    class FakeDatabase:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, statement):
            compiled = statement.compile(dialect=postgresql.dialect())
            captured["sql"] = str(compiled)
            captured["params"] = compiled.params
            return SimpleNamespace(all=lambda: [(embedding, 0.2)])

    results = vector_service.search_similar_tasks(FakeDatabase(), "user-a", "due date")
    assert results == [{"task_id": 9, "score": pytest.approx(0.8)}]
    assert "task_embeddings.user_id" in captured["sql"]
    assert "user-a" in captured["params"].values()
