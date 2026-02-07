"""Configuration management using Pydantic settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Azure AD (Microsoft Graph)
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_tenant_id: str = ""

    # Harvest (optional)
    harvest_account_id: str = ""
    harvest_access_token: str = ""

    # App
    app_secret_key: str
    app_base_url: str = "http://localhost:8000"  # Used for OAuth redirect


settings = Settings()
