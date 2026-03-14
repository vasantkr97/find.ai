from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        extra="ignore",
    )

    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    SERPER_API_KEY: str | None = None
    DATABASE_URL: str

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: HttpUrl | None = None
    NEXT_PUBLIC_APP_URL: HttpUrl | None = None

    NODE_ENV: Literal["development", "production", "test"] = "development"

    LLM_PROVIDER: Literal["openai", "gemini", "ollama"] = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    LLM_TEMPERATURE: float = Field(default=0.3, ge=0.0, le=2.0)
    LLM_MAX_TOKENS: int = Field(default=4096, gt=0)
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_BATCH_SIZE: int = Field(default=100, gt=0)

    AGENT_MAX_STEPS: int = Field(default=10, ge=1, le=30)
    AGENT_STEP_TIMEOUT_MS: int = Field(default=30_000, gt=0)
    AGENT_LLM_RETRY_ATTEMPTS: int = Field(default=3, ge=0, le=5)

    VECTOR_SIMILARITY_THRESHOLD: float = Field(default=0.3, ge=0.0, le=1.0)
    VECTOR_DEFAULT_TOP_K: int = Field(default=5, gt=0)
    VECTOR_CHUNK_SIZE: int = Field(default=1000, gt=0)
    VECTOR_CHUNK_OVERLAP: int = Field(default=200, ge=0)

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_MS: int = Field(default=60_000, gt=0)
    RATE_LIMIT_MAX_REQUESTS: int = Field(default=20, gt=0)

    WEB_SCRAPE_TIMEOUT_MS: int = Field(default=15_000, gt=0)
    WEB_SCRAPE_MAX_LENGTH: int = Field(default=8000, gt=0)

    CORS_ALLOWED_ORIGINS: str = "http://localhost:3001"

    @property
    def app_url(self) -> str:
        return str(self.NEXT_PUBLIC_APP_URL or "http://localhost:3001")

    @property
    def redirect_uri(self) -> str:
        if self.GOOGLE_REDIRECT_URI:
            return str(self.GOOGLE_REDIRECT_URI)
        return f"{self.app_url}/api/drive/callback"

    @property
    def is_prod(self) -> bool:
        return self.NODE_ENV == "production"

    @property
    def is_dev(self) -> bool:
        return self.NODE_ENV == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # BaseSettings resolves required values from environment variables at runtime.
    return Settings()  # type: ignore[call-arg]
