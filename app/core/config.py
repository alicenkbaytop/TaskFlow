from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./taskflow_dev.db"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str = "qwen2.5:3b"
    ollama_embedding_model: str = "nomic-embed-text:latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-001"
    phoenix_endpoint: str = ""
    cors_origins: str = "http://localhost:8501"


@lru_cache
def get_settings() -> Settings:
    return Settings()
