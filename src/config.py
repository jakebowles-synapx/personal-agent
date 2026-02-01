"""Configuration management using Pydantic settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str
    telegram_webhook_url: str

    # Azure OpenAI
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str = "gpt-4"
    azure_openai_embedding_deployment: str = "text-embedding-ada-002"

    # Azure AD (Microsoft Graph) - Phase 2
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_tenant_id: str = ""

    # Memory
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # App
    app_secret_key: str
    allowed_telegram_users: str = ""

    @property
    def allowed_user_ids(self) -> set[int]:
        """Parse allowed Telegram user IDs from comma-separated string."""
        if not self.allowed_telegram_users:
            return set()
        return {int(uid.strip()) for uid in self.allowed_telegram_users.split(",") if uid.strip()}


settings = Settings()
