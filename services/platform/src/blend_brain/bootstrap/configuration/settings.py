"""Application settings loaded and validated at process startup."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Supported deployment environments."""

    LOCAL = "local"
    TEST = "test"
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    """Supported log renderers."""

    JSON = "json"
    CONSOLE = "console"


class Settings(BaseSettings):
    """Strongly typed startup configuration.

    Environment variables use the uppercase form of each field name. Unknown values
    are ignored so infrastructure-level variables can coexist in the process safely.
    """

    model_config = SettingsConfigDict(
        env_prefix="BLEND_BRAIN_",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Blend Knowledge Brain API"
    app_env: AppEnvironment = AppEnvironment.LOCAL
    app_version: str = "0.1.0"
    debug: bool = False
    api_base_path: str = "/api/v1"
    docs_enabled: bool = False

    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.JSON

    cors_allowed_origins: list[str] = Field(default_factory=list)
    cors_allow_credentials: bool = True
    trusted_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )

    request_id_header: str = "X-Request-ID"

    api_auth_enabled: bool = False
    api_static_bearer_token: SecretStr | None = None
    api_static_subject: str = "local-developer"
    api_static_project_ids: list[str] = Field(default_factory=lambda: ["*"])

    otel_enabled: bool = False
    otel_service_name: str = "blend-knowledge-brain-api"
    otel_exporter_otlp_endpoint: str | None = None
    otel_trace_sample_ratio: float = Field(default=1.0, ge=0.0, le=1.0)

    openai_api_key: SecretStr | None = None
    openai_project_dna_model: str = "gpt-4.1-2025-04-14"
    openai_question_answer_model: str = "gpt-4.1-2025-04-14"
    openai_business_artifact_model: str = "gpt-4.1-2025-04-14"
    openai_embedding_model: str = "text-embedding-3-large"
    openai_embedding_dimensions: int = Field(default=3072, ge=3072, le=3072)
    openai_timeout_seconds: float = Field(default=60.0, gt=0)
    openai_max_retries: int = Field(default=3, ge=0, le=10)

    retrieval_default_top_k: int = Field(default=8, ge=1, le=50)
    retrieval_rrf_k: int = Field(default=60, ge=1)
    retrieval_dense_weight: float = Field(default=0.6, ge=0.0)
    retrieval_lexical_weight: float = Field(default=0.4, ge=0.0)
    retrieval_candidate_multiplier: int = Field(default=4, ge=1, le=20)
    retrieval_max_cached_scopes: int = Field(default=32, ge=1, le=1_000)
    retrieval_max_question_characters: int = Field(default=4_000, ge=1, le=20_000)
    retrieval_answer_max_input_tokens: int = Field(default=100_000, ge=1)

    intelligence_default_similarity_limit: int = Field(default=6, ge=1, le=50)
    intelligence_default_expert_limit: int = Field(default=8, ge=1, le=50)
    intelligence_max_expert_query_characters: int = Field(default=2_000, ge=1, le=20_000)
    intelligence_max_cached_scopes: int = Field(default=32, ge=1, le=1_000)
    intelligence_minimum_similarity: float = Field(default=0.6, ge=0.0, le=1.0)
    intelligence_minimum_expert_score: float = Field(default=0.55, ge=0.0, le=1.0)

    knowledge_max_value_characters: int = Field(default=20_000, ge=1, le=100_000)
    knowledge_max_rationale_characters: int = Field(default=4_000, ge=1, le=20_000)
    knowledge_max_source_reference_characters: int = Field(default=4_000, ge=1, le=20_000)

    artifact_max_input_tokens: int = Field(default=100_000, ge=1)
    artifact_max_brief_characters: int = Field(default=20_000, ge=1, le=100_000)
    artifact_max_projects: int = Field(default=20, ge=1, le=100)
    artifact_max_project_sources: int = Field(default=500, ge=1, le=5_000)
    artifact_max_generated_characters: int = Field(default=100_000, ge=1, le=500_000)
    artifact_max_sections_per_project: int = Field(default=100, ge=1, le=1_000)
    artifact_pdf_max_bytes: int = Field(default=15_000_000, ge=1, le=100_000_000)
    artifact_export_directory: str = ".local/artifacts"
    artifact_export_prefix: str = "business-artifacts"

    snowflake_enabled: bool = False
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: SecretStr | None = None
    snowflake_private_key_file: str | None = None
    snowflake_private_key_file_password: SecretStr | None = None
    snowflake_warehouse: str | None = None
    snowflake_database: str | None = None
    snowflake_schema: str = "KNOWLEDGE_BRAIN"
    snowflake_role: str | None = None

    @field_validator("api_base_path")
    @classmethod
    def validate_api_base_path(cls, value: str) -> str:
        """Require a normalized absolute API prefix."""
        if not value.startswith("/") or value == "/":
            msg = "API_BASE_PATH must be an absolute, non-root path"
            raise ValueError(msg)
        return value.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Restrict logging to standard severity levels."""
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            msg = f"LOG_LEVEL must be one of {sorted(allowed)}"
            raise ValueError(msg)
        return normalized

    @field_validator("request_id_header")
    @classmethod
    def validate_request_id_header(cls, value: str) -> str:
        """Reject empty or malformed HTTP header names."""
        normalized = value.strip()
        if not normalized or any(character.isspace() for character in normalized):
            msg = "REQUEST_ID_HEADER must be a valid non-empty HTTP header name"
            raise ValueError(msg)
        return normalized

    @model_validator(mode="after")
    def validate_environment_safety(self) -> Self:
        """Reject unsafe production combinations at startup."""
        if self.app_env is AppEnvironment.PRODUCTION and self.debug:
            msg = "DEBUG cannot be enabled in production"
            raise ValueError(msg)
        if self.app_env is AppEnvironment.PRODUCTION and self.log_format is not LogFormat.JSON:
            msg = "LOG_FORMAT must be json in production"
            raise ValueError(msg)
        if self.cors_allow_credentials and "*" in self.cors_allowed_origins:
            msg = "Wildcard CORS origins cannot be used with credentials"
            raise ValueError(msg)
        if "*" in self.trusted_hosts and self.app_env is AppEnvironment.PRODUCTION:
            msg = "Wildcard trusted hosts are prohibited in production"
            raise ValueError(msg)
        if self.otel_enabled and not self.otel_exporter_otlp_endpoint:
            msg = "OTEL_EXPORTER_OTLP_ENDPOINT is required when telemetry is enabled"
            raise ValueError(msg)
        if self.api_auth_enabled:
            if self.api_static_bearer_token is None:
                msg = "API_STATIC_BEARER_TOKEN is required when API authentication is enabled"
                raise ValueError(msg)
            if not self.api_static_subject.strip():
                msg = "API_STATIC_SUBJECT cannot be empty"
                raise ValueError(msg)
            if not self.api_static_project_ids or any(
                not project_id.strip() for project_id in self.api_static_project_ids
            ):
                msg = "API_STATIC_PROJECT_IDS requires non-empty project identifiers"
                raise ValueError(msg)
            if "*" in self.api_static_project_ids and len(self.api_static_project_ids) != 1:
                msg = "API_STATIC_PROJECT_IDS wildcard cannot be combined with project identifiers"
                raise ValueError(msg)
            if self.app_env is AppEnvironment.PRODUCTION:
                msg = "Static bearer authentication is prohibited in production; configure OIDC"
                raise ValueError(msg)
        if self.snowflake_enabled:
            required = {
                "SNOWFLAKE_ACCOUNT": self.snowflake_account,
                "SNOWFLAKE_USER": self.snowflake_user,
                "SNOWFLAKE_WAREHOUSE": self.snowflake_warehouse,
                "SNOWFLAKE_DATABASE": self.snowflake_database,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                msg = f"Snowflake configuration is missing: {', '.join(missing)}"
                raise ValueError(msg)
            if not self.snowflake_password and not self.snowflake_private_key_file:
                msg = "Snowflake requires password or private-key authentication"
                raise ValueError(msg)
        if self.retrieval_dense_weight + self.retrieval_lexical_weight <= 0:
            msg = "At least one retrieval weight must be greater than zero"
            raise ValueError(msg)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide validated settings instance."""
    return Settings()
