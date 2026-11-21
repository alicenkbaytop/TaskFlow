from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./taskflow_dev.db"
    database_pool_size: int = 5
    database_max_overflow: int = 5
    supabase_url: str = ""
    supabase_anon_key: str = ""
    default_ai_provider: str = "gemini"
    ai_chat_provider: str = ""
    ai_complex_provider: str = ""
    ai_important_provider: str = ""
    ai_embedding_provider: str = ""
    ai_fallback_providers: str = "openrouter,groq"
    ai_timeout_seconds: float = 30.0
    ai_retry_attempts: int = 2
    ai_retry_base_seconds: float = 0.35
    ai_embedding_cache_ttl_seconds: int = 900
    ai_embedding_cache_max_entries: int = 1024
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-001"
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-4-31b-it:free"
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    phoenix_endpoint: str = ""
    phoenix_api_key: str = ""
    ai_cooldown_seconds: int = 60
    ai_failure_threshold: int = 3
    app_environment: str = "development"
    cors_origins: str = "http://localhost:8501"

    @model_validator(mode="after")
    def require_durable_database_in_production(self):
        if (
            self.app_environment.lower() == "production"
            and self.database_url.startswith("sqlite")
        ):
            raise ValueError("Production requires PostgreSQL; SQLite is not durable")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
