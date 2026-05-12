from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "info"
    FRONTEND_URL: str = "http://localhost:3000"

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "datasharing_dev"
    POSTGRES_USER: str = "dsplatform"
    POSTGRES_PASSWORD: str = ""

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "datasharing-files"
    MINIO_SECURE: bool = False

    # Keycloak
    KEYCLOAK_SERVER_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "datasharing-dev"
    KEYCLOAK_CLIENT_ID: str = "datasharing-backend"
    KEYCLOAK_CLIENT_SECRET: str = ""
    KEYCLOAK_ADMIN_USER: str = "admin"
    KEYCLOAK_ADMIN_PASSWORD: str = "admin"

    # Email
    EMAIL_BACKEND: str = "smtp"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USE_TLS: bool = False
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@datasharing.local"
    INVITATION_FROM_EMAIL: str = "invitations@datasharing.local"

    # Super Admin seed
    SUPER_ADMIN_EMAIL: str = ""
    SUPER_ADMIN_PASSWORD: str = ""

    # File limits
    MAX_FILE_SIZE_BYTES: int = 5368709120  # 5 GB

    # Workers
    WORKER_EXPIRY_CHECK_INTERVAL_MINUTES: int = 60
    WORKER_SLA_CHECK_INTERVAL_MINUTES: int = 30
    WORKER_NOTIFICATION_INTERVAL_MINUTES: int = 5

    # IDQP — LLM client (Step 3b matcher + Step 6 Excel/NL pipeline).
    # When DQ_LLM_PROVIDER is empty or 'none', all LLM features degrade
    # gracefully — the fuzzy matcher still works, AI-only endpoints return
    # 503, and the standalone UI hides the "Draft with AI" affordance.
    #
    # Provider was Anthropic Haiku 4.5 originally; the codebase now uses
    # local Ollama by default. The abstraction in
    # data_quality/ai/client.py keeps the swap surface small.
    DQ_LLM_PROVIDER: str = "ollama"          # ollama | (future: openai/anthropic)
    DQ_LLM_BASE_URL: str = "http://host.docker.internal:11434"
    DQ_LLM_MODEL: str = "qwen2.5-coder:7b"
    DQ_LLM_MAX_OUTPUT_TOKENS: int = 1024
    DQ_LLM_TIMEOUT_S: int = 90               # cold-start can take ~30s on first call

    # External pickup portal
    PICKUP_TOKEN_TTL_HOURS: int = 72
    PICKUP_TOKEN_MAX_DOWNLOADS: int = 10
    PICKUP_DOWNLOAD_URL_TTL_SECONDS: int = 120
    PICKUP_RATE_LIMIT_PER_MINUTE: int = 30
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
