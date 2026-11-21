import hashlib
import logging
import threading
import time
from collections import OrderedDict

from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import TaskEmbedding
from app.services.model_router import (
    generate_with_fallback,
    provider_is_configured,
    provider_order,
    resolve_route,
)
from app.services.provider_reliability import with_retries

EMBEDDING_DIMENSIONS = 768
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
_cache_lock = threading.RLock()
_embedding_cache: OrderedDict[tuple[str, str, str, str], tuple[float, list[float]]] = (
    OrderedDict()
)
_cache_hits = 0
_cache_misses = 0


def embedding_provider_configured() -> bool:
    return provider_is_configured(resolve_route("embedding"))


def _cache_key(user_id: str | None, provider: str, model: str, text: str):
    return (
        user_id or "anonymous",
        provider,
        model,
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _cached_embedding(key):
    global _cache_hits, _cache_misses
    now = time.monotonic()
    with _cache_lock:
        cached = _embedding_cache.get(key)
        if cached and cached[0] > now:
            _cache_hits += 1
            _embedding_cache.move_to_end(key)
            return list(cached[1])
        if cached:
            del _embedding_cache[key]
        _cache_misses += 1
        return None


def _store_embedding(key, vector: list[float]) -> None:
    settings = get_settings()
    if settings.ai_embedding_cache_max_entries <= 0:
        return
    expires = time.monotonic() + max(0, settings.ai_embedding_cache_ttl_seconds)
    with _cache_lock:
        _embedding_cache[key] = (expires, list(vector))
        _embedding_cache.move_to_end(key)
        while len(_embedding_cache) > settings.ai_embedding_cache_max_entries:
            _embedding_cache.popitem(last=False)


def invalidate_embedding_cache(user_id: str, text: str) -> None:
    key_text = hashlib.sha256(text.encode("utf-8")).hexdigest()
    with _cache_lock:
        stale_keys = [
            key for key in _embedding_cache if key[0] == user_id and key[3] == key_text
        ]
        for key in stale_keys:
            del _embedding_cache[key]


def embedding_cache_info() -> dict[str, int]:
    with _cache_lock:
        return {
            "hits": _cache_hits,
            "misses": _cache_misses,
            "entries": len(_embedding_cache),
        }


def _request_embedding(route, text: str):
    settings = get_settings()
    if route.provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=int(settings.ai_timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        result = client.models.embed_content(
            model=route.model,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
        )
        vector = result.embeddings[0].values
    else:
        raise RuntimeError(f"Unsupported embedding provider: {route.provider}")
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Embedding provider returned {len(vector)} dimensions; "
            f"expected {EMBEDDING_DIMENSIONS}"
        )
    return list(vector)


def create_embedding(text: str, user_id: str | None = None) -> list[float]:
    route = resolve_route("embedding")
    key = _cache_key(user_id, route.provider, route.model, text)
    cached = _cached_embedding(key)
    if cached is not None:
        with tracer.start_as_current_span("ai.embedding") as span:
            span.set_attribute("ai.provider", route.provider)
            span.set_attribute("ai.model", route.model)
            span.set_attribute("cache.hit", True)
            span.set_attribute("ai.latency_ms", 0.0)
        logger.info(
            "Embedding cache hit provider=%s model=%s", route.provider, route.model
        )
        return cached

    settings = get_settings()
    start = time.perf_counter()
    with tracer.start_as_current_span("ai.embedding") as span:
        span.set_attribute("ai.provider", route.provider)
        span.set_attribute("ai.model", route.model)
        span.set_attribute("cache.hit", False)
        actual_route = route
        try:
            (vector, attempts), actual_route = generate_with_fallback(
                lambda candidate: with_retries(
                    lambda: _request_embedding(candidate, text),
                    attempts=settings.ai_retry_attempts,
                    base_delay_seconds=settings.ai_retry_base_seconds,
                ),
                routes=provider_order("embedding", route.provider),
            )
            span.set_attribute("ai.fallback_used", actual_route != route)
            duration = (time.perf_counter() - start) * 1000
            span.set_attribute("ai.retry_count", attempts - 1)
            span.set_attribute("ai.success", True)
            span.set_attribute("ai.latency_ms", duration)
            span.set_attribute("ai.provider", actual_route.provider)
            span.set_attribute("ai.model", actual_route.model)
            _store_embedding(
                _cache_key(user_id, actual_route.provider, actual_route.model, text),
                vector,
            )
            return vector
        except Exception as error:
            span.set_attribute("ai.success", False)
            span.set_attribute("error.type", type(error).__name__)
            span.set_attribute("ai.latency_ms", (time.perf_counter() - start) * 1000)
            raise


def index_task(
    db: Session, user_id: str, task_id: int, title: str, description: str | None
):
    content = f"Title: {title}\nDescription: {description or ''}"
    vector = create_embedding(content, user_id=user_id)
    row = db.get(TaskEmbedding, task_id)
    if row is None:
        row = TaskEmbedding(
            task_id=task_id, user_id=user_id, content=content, embedding=vector
        )
        db.add(row)
    else:
        row.user_id, row.content, row.embedding = user_id, content, vector
    db.commit()


def delete_task_vector(db: Session, task_id: int):
    row = db.get(TaskEmbedding, task_id)
    if row:
        db.delete(row)
        db.commit()


def search_similar_tasks(db: Session, user_id: str, query: str, limit: int = 5):
    if db.bind.dialect.name != "postgresql":
        raise RuntimeError("Semantic search requires PostgreSQL with pgvector")
    start = time.perf_counter()
    with tracer.start_as_current_span("ai.retrieval") as span:
        try:
            vector = create_embedding(query, user_id=user_id)
            distance = TaskEmbedding.embedding.cosine_distance(vector)
            rows = db.execute(
                select(TaskEmbedding, distance.label("distance"))
                .where(TaskEmbedding.user_id == user_id)
                .order_by(distance)
                .limit(limit)
            ).all()
            results = [
                {"task_id": row.task_id, "score": 1 - float(distance)}
                for row, distance in rows
                if distance is not None
            ]
            span.set_attribute("retrieval.result_count", len(results))
            span.set_attribute("retrieval.success", True)
            return results
        except Exception as error:
            span.set_attribute("retrieval.success", False)
            span.set_attribute("error.type", type(error).__name__)
            raise
        finally:
            span.set_attribute(
                "retrieval.latency_ms", (time.perf_counter() - start) * 1000
            )
