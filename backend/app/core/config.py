from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql://tender:tender@localhost:5432/tender_platform"

    # Object storage
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "tenders"

    # AI providers — Ollama Cloud via a local daemon, no separate API key
    # (docs/DECISIONS.md #28)
    use_local_vision: bool = False
    ollama_base_url: str = "http://localhost:11434"

    # Queue / cache
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str = "change-me-in-every-environment"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    # Upload limits
    max_upload_pages: int = 2000
    max_upload_size_mb: int = 500


settings = Settings()
