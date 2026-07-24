"""Phase 8 proposal, one-pager, and PDF export composition."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from openai import OpenAI

from blend_brain.bootstrap.configuration import Settings
from blend_brain.business_artifacts.application import (
    GenerationLimits,
    OnePagerGenerationService,
    PdfExportService,
    ProposalGenerationService,
)
from blend_brain.business_artifacts.infrastructure import (
    LocalArtifactObjectStore,
    OpenAIBusinessArtifactGenerator,
    ReportLabPdfRenderer,
    SnowflakeBusinessArtifactRepository,
    UtcClock,
    Uuid4Generator,
)
from blend_brain.knowledge_enrichment.infrastructure import SnowflakeConnectionFactory
from blend_brain.knowledge_enrichment.infrastructure.snowflake import SnowflakeConnectionConfig

if TYPE_CHECKING:
    from blend_brain.business_artifacts.infrastructure.snowflake import ConnectionFactory


@dataclass(frozen=True, slots=True)
class BusinessArtifactServices:
    """Phase 8 services exposed only to trusted orchestration layers."""

    proposals: ProposalGenerationService
    one_pagers: OnePagerGenerationService
    pdf_exports: PdfExportService


def create_business_artifact_services(settings: Settings) -> BusinessArtifactServices:
    """Build Phase 8 services with local PDF storage."""
    if settings.openai_api_key is None:
        raise ValueError("BLEND_BRAIN_OPENAI_API_KEY is required for Phase 8")
    if not settings.snowflake_enabled:
        raise ValueError("BLEND_BRAIN_SNOWFLAKE_ENABLED must be true for Phase 8")
    if not all(
        (
            settings.snowflake_account,
            settings.snowflake_user,
            settings.snowflake_warehouse,
            settings.snowflake_database,
        )
    ):
        raise ValueError("Snowflake settings are incomplete")
    config = SnowflakeConnectionConfig(
        account=cast("str", settings.snowflake_account),
        user=cast("str", settings.snowflake_user),
        warehouse=cast("str", settings.snowflake_warehouse),
        database=cast("str", settings.snowflake_database),
        schema=settings.snowflake_schema,
        role=settings.snowflake_role,
        password=(
            settings.snowflake_password.get_secret_value() if settings.snowflake_password else None
        ),
        private_key_file=settings.snowflake_private_key_file,
        private_key_file_password=(
            settings.snowflake_private_key_file_password.get_secret_value()
            if settings.snowflake_private_key_file_password
            else None
        ),
        query_tag="blend-knowledge-brain:phase-8",
    )
    connection_factory = cast("ConnectionFactory", SnowflakeConnectionFactory(config))
    repository = SnowflakeBusinessArtifactRepository(
        connection_factory,
        database=config.database,
        schema=config.schema,
        max_sections_per_project=settings.artifact_max_sections_per_project,
    )
    client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )
    generator = OpenAIBusinessArtifactGenerator(
        client,
        model=settings.openai_business_artifact_model,
        max_input_tokens=settings.artifact_max_input_tokens,
    )
    clock = UtcClock()
    limits = GenerationLimits(
        max_brief_characters=settings.artifact_max_brief_characters,
        max_projects=settings.artifact_max_projects,
        max_project_sources=settings.artifact_max_project_sources,
        max_generated_characters=settings.artifact_max_generated_characters,
    )
    object_store = LocalArtifactObjectStore(settings.artifact_export_directory)
    return BusinessArtifactServices(
        proposals=ProposalGenerationService(generator, repository, clock, limits),
        one_pagers=OnePagerGenerationService(generator, repository, clock, limits),
        pdf_exports=PdfExportService(
            repository,
            ReportLabPdfRenderer(),
            object_store,
            clock,
            Uuid4Generator(),
            object_prefix=settings.artifact_export_prefix,
            max_pdf_bytes=settings.artifact_pdf_max_bytes,
        ),
    )
