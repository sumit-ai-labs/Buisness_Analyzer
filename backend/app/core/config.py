import os
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables or .env file."""

    _backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    model_config = SettingsConfigDict(
        env_file=(os.path.join(_backend_dir, ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server Configuration
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    ENV: str = "development"

    # JWT Authentication
    JWT_SECRET_KEY: str = "development_secret_key_business_disruption_warning_system_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Single-Tenant Admin User (Default for MVP)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeg6Lruj3vjPGga31lW"  # bcrypt hash of 'admin123'

    # Research Agent Configuration (Tavily API)
    TAVILY_API_KEY: str = ""
    SEARCH_RECENCY_DAYS: int = 7  # Max age of news results (Tavily `days` param + post-fetch filter)
    SEARCH_KEEP_UNDATED_RESULTS: bool = False

    # Analysis Agent Configuration (Gemini / OpenAI / Anthropic)
    LLM_PROVIDER: Literal["gemini", "openai", "anthropic"] = "gemini"
    GEMINI_API_KEY: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-3.8-flash"
    # Shadow Evaluation Configuration (records proposed alerts without altering operational state)
    SHADOW_MODE: bool = False

    @property
    def has_tavily_key(self) -> bool:
        return bool(self.TAVILY_API_KEY and self.TAVILY_API_KEY.strip())

    @property
    def has_llm_key(self) -> bool:
        return bool(
            (self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip())
            or (self.LLM_API_KEY and self.LLM_API_KEY.strip())
        )


# Global settings singleton
settings = Settings()
