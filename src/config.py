"""Configuration management using Pydantic settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Azure OpenAI
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str = "gpt-4"
    azure_openai_embedding_deployment: str = "text-embedding-ada-002"

    # Azure AD (Microsoft Graph)
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_tenant_id: str = ""

    # Harvest
    harvest_account_id: str = ""
    harvest_access_token: str = ""

    # Memory
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # App
    app_secret_key: str
    app_base_url: str = "http://localhost:8000"  # Used for OAuth redirect
    data_dir: str = "."  # Directory for SQLite databases


settings = Settings()
