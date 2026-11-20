from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class ModelRoute:
    operation: str
    provider: str
    model: str
    fallback_provider: str | None = None
    fallback_model: str | None = None


def _model_for(provider: str, operation: str) -> str:
    settings = get_settings()
    if provider == "ollama":
        return (
            settings.ollama_embedding_model
            if operation == "embedding"
            else settings.ollama_model
        )
    if provider == "gemini":
        return (
            settings.gemini_embedding_model
            if operation == "embedding"
            else settings.gemini_model
        )
    raise ValueError(f"Unsupported AI provider: {provider}")


def resolve_route(operation: str) -> ModelRoute:
    if operation not in {"chat", "embedding", "evaluation"}:
        raise ValueError(f"Unsupported AI operation: {operation}")

    settings = get_settings()
    provider_setting = (
        settings.ai_embedding_provider
        if operation == "embedding"
        else settings.ai_chat_provider
    )
    provider = (provider_setting or settings.ai_provider).strip().lower()
    model = _model_for(provider, operation)

    fallback_provider = settings.ai_fallback_provider.strip().lower() or None
    if fallback_provider == provider:
        fallback_provider = None
    fallback_model = (
        _model_for(fallback_provider, operation) if fallback_provider else None
    )

    return ModelRoute(
        operation=operation,
        provider=provider,
        model=model,
        fallback_provider=fallback_provider,
        fallback_model=fallback_model,
    )


def fallback_route(route: ModelRoute) -> ModelRoute | None:
    if not route.fallback_provider or not route.fallback_model:
        return None
    return ModelRoute(
        operation=route.operation,
        provider=route.fallback_provider,
        model=route.fallback_model,
    )
