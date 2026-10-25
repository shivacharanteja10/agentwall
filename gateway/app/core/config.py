"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "AgentWall"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://agentwall:agentwall@localhost:5432/agentwall",
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Security
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for JWT signing",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # API Keys
    api_key_header: str = "X-API-Key"

    # Upstream tool servers
    filesystem_server_url: str = "http://localhost:8001"
    database_server_url: str = "http://localhost:8002"
    web_fetch_server_url: str = "http://localhost:8003"

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # Approval queue
    approval_timeout_seconds: int = 300

    # Audit
    audit_hash_algorithm: str = "sha256"

    # Threat detection
    enable_ml_classifier: bool = False
    ml_model_path: Optional[str] = None

    # DLP
    enable_dlp: bool = True

    # Egress allowlist (comma-separated)
    egress_allowlist: str = "http://localhost:8001,http://localhost:8002,http://localhost:8003"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # CORS
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )

    @property
    def egress_allowlist_parsed(self) -> list[str]:
        """Parse egress allowlist from comma-separated string."""
        return [url.strip() for url in self.egress_allowlist.split(",") if url.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
