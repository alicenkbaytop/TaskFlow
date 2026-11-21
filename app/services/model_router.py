"""Central provider selection and bounded fallback for model requests."""

import time
from dataclasses import dataclass

from opentelemetry import trace

from app.core.config import get_settings

tracer = trace.get_tracer(__name__)
PROVIDERS = ("gemini", "openrouter", "groq")
MODEL_CAPABILITIES = {
    ("openrouter", "google/gemma-4-31b-it:free"): {
        "tool_calling": True,
        "json_mode": True,
        "json_schema": False,
        "context_tokens": 262_144,
        "max_output_tokens": 32_768,
    },
    ("groq", "qwen/qwen3.8-27b"): {
        "tool_calling": True,
        "json_mode": True,
        "json_schema": True,
        "context_tokens": 131_072,
        "max_output_tokens": 16_384,
    },
}


@dataclass(frozen=True)
class ModelRoute:
    operation: str
    provider: str
    model: str


def _model_for(provider: str, operation: str) -> str:
    settings = get_settings()
    if operation == "embedding":
        if provider != "gemini":
            raise ValueError(
                f"Provider {provider} does not support TaskFlow embeddings"
            )
        return settings.gemini_embedding_model
    models = {
        "gemini": settings.gemini_model,
        "openrouter": settings.openrouter_model,
        "groq": settings.groq_model,
    }
    try:
        return models[provider]
    except KeyError as error:
        raise ValueError(f"Unsupported AI provider: {provider}") from error


def resolve_route(operation: str, provider: str | None = None) -> ModelRoute:
    if operation not in {"chat", "embedding", "evaluation"}:
        raise ValueError(f"Unsupported AI operation: {operation}")
    settings = get_settings()
    preferred = (
        provider
        or (
            settings.ai_embedding_provider
            if operation == "embedding"
            else settings.ai_chat_provider
        )
        or settings.default_ai_provider
    )
    preferred = preferred.strip().lower()
    if preferred not in PROVIDERS:
        raise ValueError(f"Unsupported AI provider: {preferred}")
    return ModelRoute(operation, preferred, _model_for(preferred, operation))


def provider_order(operation: str, preferred: str | None = None) -> list[ModelRoute]:
    """Return selected provider followed by configured fallback candidates."""
    settings = get_settings()
    first = resolve_route(operation, preferred)
    configured = settings.ai_fallback_providers
    fallbacks = [part.strip().lower() for part in configured.split(",") if part.strip()]
    if not fallbacks:
        fallbacks = [provider for provider in PROVIDERS if provider != first.provider]
    result = [first]
    seen = {first.provider}
    for provider in [
        *fallbacks,
        *(name for name in PROVIDERS if name not in fallbacks),
    ]:
        if provider in seen:
            continue
        if provider not in PROVIDERS:
            raise ValueError(f"Unsupported AI provider in fallback list: {provider}")
        if operation == "embedding" and provider != "gemini":
            continue
        result.append(resolve_route(operation, provider))
        seen.add(provider)
    return result


def task_importance(message: str) -> str:
    text = message.casefold()
    if any(
        verb in text
        for verb in (
            "create",
            "add",
            "update",
            "change",
            "complete",
            "delete",
            "remove",
        )
    ):
        return "important"
    if len(text.split()) > 45 or any(
        marker in text for marker in ("compare", "plan", "prioritize", "step by step")
    ):
        return "complex"
    return "normal"


def model_capabilities(route: ModelRoute) -> dict:
    if route.provider == "gemini":
        return {
            "tool_calling": True,
            "json_mode": True,
            "json_schema": True,
            "context_tokens": None,
            "max_output_tokens": None,
        }
    return MODEL_CAPABILITIES.get(
        (route.provider, route.model),
        {
            "tool_calling": False,
            "json_mode": False,
            "json_schema": False,
            "context_tokens": None,
            "max_output_tokens": None,
        },
    )


def route_for_task(message: str) -> tuple[ModelRoute, str]:
    settings = get_settings()
    importance = task_importance(message)
    configured = {
        "complex": settings.ai_complex_provider,
        "important": settings.ai_important_provider,
    }.get(importance, "")
    route = resolve_route("chat", configured or None)
    with tracer.start_as_current_span("ai.routing_decision") as span:
        span.set_attribute("ai.task_importance", importance)
        span.set_attribute("ai.provider", route.provider)
        span.set_attribute("ai.model", route.model)
        span.set_attribute("ai.has_explicit_preference", bool(configured))
    return route, importance


def provider_is_configured(route: ModelRoute) -> bool:
    settings = get_settings()
    return bool(
        {
            "gemini": settings.gemini_api_key,
            "openrouter": settings.openrouter_api_key,
            "groq": settings.groq_api_key,
        }[route.provider]
    )


def generate_with_fallback(operation, *, routes: list[ModelRoute] | None = None):
    """Run generation only; callers execute returned tool calls exactly once."""
    routes = routes or provider_order("chat")
    last_error = None
    from app.services.provider_reliability import (
        is_fallback_eligible,
        provider_available,
        record_provider_result,
    )

    previous_attempt = None
    for index, route in enumerate(routes):
        if not provider_available(route.provider):
            continue
        if route.operation == "embedding" and route.provider != "gemini":
            last_error = RuntimeError("TaskFlow embeddings are pinned to Gemini")
            continue
        capabilities = model_capabilities(route)
        unsupported = (
            route.operation == "chat" and not capabilities["tool_calling"]
        ) or (route.operation == "evaluation" and not capabilities["json_mode"])
        if unsupported:
            last_error = RuntimeError(
                f"Configured {route.provider} model lacks the required "
                f"capability for {route.operation}"
            )
            continue
        if not provider_is_configured(route):
            last_error = RuntimeError(
                f"{route.provider.upper()}_API_KEY is not configured"
            )
            continue
        with tracer.start_as_current_span("ai.routing_attempt") as span:
            attempt_start = time.perf_counter()
            span.set_attribute("ai.operation", route.operation)
            span.set_attribute("ai.provider", route.provider)
            span.set_attribute("ai.model", route.model)
            span.set_attribute("ai.fallback", index > 0)
            try:
                result = operation(route)
                record_provider_result(route.provider, True)
                span.set_attribute("ai.success", True)
                span.set_attribute(
                    "ai.latency_ms", (time.perf_counter() - attempt_start) * 1000
                )
                if previous_attempt:
                    span.set_attribute("ai.fallback_from", previous_attempt)
                return result, route
            except Exception as error:
                span.set_attribute("ai.success", False)
                span.set_attribute("error.type", type(error).__name__)
                status = getattr(error, "status_code", None) or getattr(
                    error, "code", None
                )
                span.set_attribute("http.status_code", status or 0)
                span.set_attribute(
                    "ai.latency_ms", (time.perf_counter() - attempt_start) * 1000
                )
                last_error = error
                previous_attempt = route.provider
                if is_fallback_eligible(error):
                    record_provider_result(route.provider, False)
                if not is_fallback_eligible(error):
                    raise
    if last_error:
        raise last_error
    raise RuntimeError("No configured AI provider is available")
