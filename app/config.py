import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    url: str = "postgresql+asyncpg://matryoshka:matryoshka_pass@localhost:5432/matryoshka_db"

    model_config = SettingsConfigDict(env_prefix="db_", env_file=".env", extra="ignore")


class OpenRouterSettings(BaseSettings):
    api_key: str = ""
    model: str = "anthropic/claude-3.5-sonnet"
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(env_prefix="openrouter_", env_file=".env", extra="ignore")


class RegulatorServiceSettings(BaseSettings):
    app_name: str = "Matryoshka Regulator Service"
    rest_host: str = "0.0.0.0"
    rest_port: int = 8002
    grpc_port: int = 50052
    debug: bool = False
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_prefix="service_", env_file=".env", extra="ignore")


database_settings = DatabaseSettings()
openrouter_settings = OpenRouterSettings()
regulator_settings = RegulatorServiceSettings()
