from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env", _API_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    public_app_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("FRONTEND_URL", "PUBLIC_APP_URL"),
    )
    api_base_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("BACKEND_URL", "API_BASE_URL"),
    )
    database_url: str = Field(
        default="postgresql+psycopg://mradi:mradi@localhost:5432/mradi",
        validation_alias="DATABASE_URL",
    )
    auto_create_tables: bool = Field(default=False, validation_alias="AUTO_CREATE_TABLES")

    clerk_issuer: str = Field(default="", validation_alias="CLERK_ISSUER")
    clerk_jwks_url: str = Field(default="", validation_alias="CLERK_JWKS_URL")
    clerk_audience: str = Field(default="", validation_alias="CLERK_AUDIENCE")
    auth_secret: str = Field(default="", validation_alias="AUTH_SECRET")
    auth_bypass: bool = Field(default=False, validation_alias="AUTH_BYPASS")
    auth_allowed_algorithm: str = Field(default="RS256", validation_alias="AUTH_ALLOWED_ALGORITHM")

    storage_backend: str = Field(default="local", validation_alias="STORAGE_BACKEND")
    local_storage_root: Path = Field(default=Path("./local-storage"), validation_alias="LOCAL_STORAGE_ROOT")
    gcs_bucket: str = Field(default="", validation_alias=AliasChoices("GCS_BUCKET_NAME", "GCS_BUCKET"))
    gcp_project_id: str = Field(default="", validation_alias=AliasChoices("GOOGLE_CLOUD_PROJECT", "GCP_PROJECT_ID"))
    gcp_location: str = Field(default="us", validation_alias=AliasChoices("DOCUMENT_AI_LOCATION", "GCP_LOCATION"))

    document_ai_processor_id: str = Field(default="", validation_alias="DOCUMENT_AI_PROCESSOR_ID")
    google_api_key: str = Field(default="", validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"))
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")
    google_genai_use_vertexai: bool = Field(default=True, validation_alias="GOOGLE_GENAI_USE_VERTEXAI")
    vertex_ai_location: str = Field(default="us-central1", validation_alias="VERTEX_AI_LOCATION")
    vertex_ai_agent_engine_resource: str = Field(default="", validation_alias="VERTEX_AI_AGENT_ENGINE_RESOURCE")
    adk_agent_config: str = Field(default="", validation_alias="ADK_AGENT_CONFIG")

    upload_signing_secret: str = Field(default="dev-only-upload-secret-change-me", validation_alias="UPLOAD_SIGNING_SECRET")
    report_signing_secret: str = Field(default="dev-only-report-secret-change-me", validation_alias="REPORT_SIGNING_SECRET")
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")
    csrf_cookie_name: str = Field(default="csrf_token", validation_alias="CSRF_COOKIE_NAME")
    csrf_header_name: str = Field(default="x-csrf-token", validation_alias="CSRF_HEADER_NAME")
    content_security_policy: str = Field(
        default=(
            "default-src 'none'; "
            "base-uri 'none'; "
            "frame-ancestors 'none'; "
            "form-action 'none'; "
            "img-src 'self' data:; "
            "style-src 'self'; "
            "script-src 'self'; "
            "connect-src 'self'"
        ),
        validation_alias="CONTENT_SECURITY_POLICY",
    )
    rate_limit_per_minute: int = Field(default=120, validation_alias="RATE_LIMIT_PER_MINUTE")
    max_upload_bytes: int = Field(default=25_000_000, validation_alias="MAX_UPLOAD_BYTES")
    max_local_upload_memory_bytes: int = Field(default=1_048_576, validation_alias="MAX_LOCAL_UPLOAD_MEMORY_BYTES")
    persist_raw_extraction_payloads: bool = Field(default=False, validation_alias="PERSIST_RAW_EXTRACTION_PAYLOADS")
    enable_malware_scan: bool = Field(default=False, validation_alias="ENABLE_MALWARE_SCAN")
    clamd_host: str = Field(default="localhost", validation_alias="CLAMD_HOST")
    clamd_port: int = Field(default=3310, validation_alias="CLAMD_PORT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    otel_exporter_otlp_endpoint: str = Field(default="", validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    sentry_dsn: str = Field(default="", validation_alias=AliasChoices("SENTRY_DSN", "ERROR_MONITORING_DSN"))
    sentry_traces_sample_rate: float = Field(default=0.0, validation_alias="SENTRY_TRACES_SAMPLE_RATE")
    sentry_profiles_sample_rate: float = Field(default=0.0, validation_alias="SENTRY_PROFILES_SAMPLE_RATE")
    state_department_lands_gazette_url: str = Field(default="", validation_alias="STATE_DEPARTMENT_LANDS_GAZETTE_URL")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def document_ai_enabled(self) -> bool:
        return bool(self.gcp_project_id and self.gcp_location and self.document_ai_processor_id)

    @property
    def gemini_vision_enabled(self) -> bool:
        return bool(self.google_api_key or (self.google_genai_use_vertexai and self.gcp_project_id))

    @property
    def gcs_enabled(self) -> bool:
        return self.storage_backend == "gcs" and bool(self.gcs_bucket)

    @property
    def kenya_gazette_url(self) -> AnyHttpUrl | str:
        return "https://new.kenyalaw.org/gazettes/"

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        if self.auth_secret:
            if self.upload_signing_secret.startswith(("dev-only-", "replace-with-")):
                self.upload_signing_secret = self.auth_secret
            if self.report_signing_secret.startswith(("dev-only-", "replace-with-")):
                self.report_signing_secret = self.auth_secret

        if not self.is_production:
            return self

        errors: list[str] = []
        if self.auth_bypass:
            errors.append("AUTH_BYPASS must be false in production")
        if not self.auth_secret and (
            self.upload_signing_secret.startswith(("dev-only-", "replace-with-"))
            or self.report_signing_secret.startswith(("dev-only-", "replace-with-"))
        ):
            errors.append("AUTH_SECRET or strong upload/report signing secrets are required in production")
        if not self.clerk_issuer or not self.clerk_jwks_url:
            errors.append("CLERK_ISSUER and CLERK_JWKS_URL are required in production")
        if self.auth_allowed_algorithm != "RS256":
            errors.append("AUTH_ALLOWED_ALGORITHM must remain RS256 in production")
        if not self.public_app_url.startswith("https://"):
            errors.append("PUBLIC_APP_URL must use HTTPS in production")
        if not self.api_base_url.startswith("https://"):
            errors.append("API_BASE_URL must use HTTPS in production")
        if any(origin == "*" for origin in self.cors_origin_list):
            errors.append("CORS_ORIGINS must not include wildcard origins in production")
        for name, value in {
            "UPLOAD_SIGNING_SECRET": self.upload_signing_secret,
            "REPORT_SIGNING_SECRET": self.report_signing_secret,
        }.items():
            if value.startswith("dev-only-") or value.startswith("replace-with-") or len(value) < 32:
                errors.append(f"{name} must be set to a strong environment-provided secret in production")
        if "mradi:mradi@" in self.database_url or "localhost" in self.database_url:
            errors.append("DATABASE_URL must be an environment-provided production database URL")
        if self.auto_create_tables:
            errors.append("AUTO_CREATE_TABLES must be false in production; run Alembic migrations explicitly")
        if self.storage_backend != "gcs":
            errors.append("STORAGE_BACKEND must be gcs in production")
        if self.storage_backend == "gcs" and not self.gcs_bucket:
            errors.append("GCS_BUCKET_NAME is required when STORAGE_BACKEND=gcs")

        if errors:
            raise ValueError("; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
