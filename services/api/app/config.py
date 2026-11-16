"""API settings from the environment (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    web_origin: str = "http://localhost:3000"
    log_level: str = "info"
    # Small pool: Render free has little RAM and Supabase free caps connections.
    db_pool_size: int = 5
    # POST /strategy/simulate limits (decision 0023): per client and across all clients.
    simulate_per_minute: int = 10
    simulate_global_per_minute: int = 120

    # LLM providers (decision 0026). A provider without a key is skipped; with none, chat
    # answers 503 "not configured" and everything else keeps working.
    groq_api_key: str = ""
    gemini_api_key: str = ""
    # "provider" or "provider:model"; quotas are per model, so the Groq models add up
    # (decision 0036). Groq's free tier gives each model about 200k tokens a day.
    llm_chain: str = "groq:openai/gpt-oss-120b,groq:qwen/qwen3.8-27b,groq:openai/gpt-oss-20b,gemini"
    groq_model: str = "openai/gpt-oss-120b"
    gemini_model: str = "gemini-2.5-flash"

    # Chat limits (decision 0032): per minute in memory, per day in Postgres.
    chat_guest_per_minute: int = 5
    chat_guest_per_day: int = 30
    chat_user_per_minute: int = 10
    chat_user_per_day: int = 100
    # Sized to what the free models can serve: ~600k Groq tokens a day at ~4k per chat
    # (decision 0036). Above it users see a clear daily-limit message, not "busy".
    chat_global_per_day: int = 150

    # Supabase Auth (decision 0030): the API validates sign-in tokens via /auth/v1/user.
    supabase_url: str = ""
    supabase_anon_key: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.web_origin.split(",") if o.strip()]

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
