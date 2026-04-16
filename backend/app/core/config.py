"""Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "Claude Simulator"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/claude_simulator"

    # AWS
    aws_region: str = "us-east-1"
    bedrock_region: str = "us-east-1"

    # Auth / Keycloak
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "claude-simulator"
    keycloak_client_id: str = "claude-simulator-app"

    # SES
    ses_region: str = "us-east-1"
    ses_sender_email: str = "noreply@example.com"
    ses_recipient_email: str = "user@example.com"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Session
    idle_timeout_minutes: int = 5
    conversation_retention_days: int = 30

    model_config = {"env_prefix": "CLAUDE_SIM_", "env_file": ".env"}


settings = Settings()
