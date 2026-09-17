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

    # Auth — single shared credential, not a per-user table (docs/DECISIONS.md #44):
    # the spec's own DDL has no users table and explicitly excludes full RBAC ("JWT
    # auth only; single internal bid-team user class"). auth_password_hash is a bcrypt
    # hash, never the plaintext password — the default below hashes the same
    # "change-me-in-every-environment" placeholder convention as jwt_secret_key.
    jwt_secret_key: str = "change-me-in-every-environment"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    auth_username: str = "admin"
    auth_password_hash: str = "$2b$12$m/yzg/ptf/eyxWW5KhX4vufwQB5jRo8J4JpfxGcSHsb1RNMRR4cBK"
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300

    # Tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    # Upload limits
    max_upload_pages: int = 2000
    max_upload_size_mb: int = 500

    # CORS — the Next.js frontend (frontend/, Phase 8) runs on a different origin
    # (:3000) than this API (:8000); without an explicit allowlist here, every
    # browser request from it is blocked by the browser itself before this app ever
    # sees it. Comma-separated, not a JSON list, so it's a plain string in .env.
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()
