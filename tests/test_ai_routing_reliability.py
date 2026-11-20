from types import SimpleNamespace

import pytest

from app.services import model_router, provider_reliability, vector_service


def test_model_routing_separates_chat_and_embeddings(monkeypatch):
    settings = SimpleNamespace(
        ai_provider="gemini",
        ai_chat_provider="ollama",
        ai_embedding_provider="gemini",
        ai_fallback_provider="ollama",
        ollama_model="local-chat",
        ollama_embedding_model="local-embed",
        gemini_model="cloud-chat",
        gemini_embedding_model="cloud-embed",
    )
    monkeypatch.setattr(model_router, "get_settings", lambda: settings)
    assert model_router.resolve_route("chat").model == "local-chat"
    embedding = model_router.resolve_route("embedding")
    assert embedding.model == "cloud-embed"
    assert model_router.fallback_route(embedding).model == "local-embed"


def test_retries_are_bounded_and_backoff_is_injectable():
    calls = []
    delays = []

    class APIError(Exception):
        status_code = 503

    def call():
        calls.append(1)
        if len(calls) < 3:
            raise APIError()
        return "ok"

    result, attempts = provider_reliability.with_retries(
        call,
        attempts=3,
        base_delay_seconds=0.2,
        sleep=delays.append,
        random_value=lambda: 0.5,
    )
    assert (result, attempts, delays) == ("ok", 3, [0.2, 0.4])


def test_retry_does_not_repeat_non_retryable_errors():
    class BadRequest(Exception):
        status_code = 400

    calls = []

    def call():
        calls.append(1)
        raise BadRequest()

    with pytest.raises(BadRequest):
        provider_reliability.with_retries(call, attempts=4, base_delay_seconds=0)
    assert len(calls) == 1


def test_embedding_cache_is_user_scoped_and_invalidated(monkeypatch):
    monkeypatch.setattr(
        vector_service,
        "get_settings",
        lambda: SimpleNamespace(
            ai_embedding_cache_max_entries=10,
            ai_embedding_cache_ttl_seconds=60,
        ),
    )
    vector_service._embedding_cache.clear()
    text = "Title: private task"
    key_a = vector_service._cache_key("user-a", "gemini", "embed-v1", text)
    key_b = vector_service._cache_key("user-b", "gemini", "embed-v1", text)
    vector_service._store_embedding(key_a, [0.1] * 768)
    vector_service._store_embedding(key_b, [0.2] * 768)

    vector_service.invalidate_embedding_cache("user-a", text)
    assert vector_service._cached_embedding(key_a) is None
    assert vector_service._cached_embedding(key_b) == [0.2] * 768
