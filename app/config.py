import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    url: str = (
        os.getenv("DATABASE_URL")
        or os.getenv("DB_URL")
        or "postgresql+asyncpg://matryoshka:matryoshka_pass@localhost:5432/matryoshka_db"
    )

    model_config = SettingsConfigDict(env_prefix="db_", env_file=".env", extra="ignore")


class OpenRouterSettings(BaseSettings):
    api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    model: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_seconds: float = 35.0

    model_config = SettingsConfigDict(env_prefix="openrouter_", env_file=".env", extra="ignore")


class ExternalServicesSettings(BaseSettings):
    analytics_service_url: str = os.getenv("ANALYTICS_SERVICE_URL", "http://analytics-service:8003")
    enterprise_service_url: str = os.getenv("ENTERPRISE_SERVICE_URL", "http://enterprise-service:8001")

    model_config = SettingsConfigDict(env_prefix="external_", env_file=".env", extra="ignore")


class RegulatorServiceSettings(BaseSettings):
    app_name: str = "Matryoshka Regulator Service"
    rest_host: str = "0.0.0.0"  # noqa: S104 - internal container interface binding
    rest_port: int = 8002
    grpc_port: int = 50052
    debug: bool = False
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    model_config = SettingsConfigDict(env_prefix="service_", env_file=".env", extra="ignore")


database_settings = DatabaseSettings()
openrouter_settings = OpenRouterSettings()
external_settings = ExternalServicesSettings()
regulator_settings = RegulatorServiceSettings()
