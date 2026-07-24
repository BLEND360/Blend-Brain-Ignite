"""Phase 7 governed knowledge lifecycle dependency composition."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from blend_brain.bootstrap.configuration import Settings
from blend_brain.knowledge_enrichment.infrastructure import SnowflakeConnectionFactory
from blend_brain.knowledge_enrichment.infrastructure.snowflake import SnowflakeConnectionConfig
from blend_brain.knowledge_lifecycle.application import (
    CaptureLimits,
    KnowledgeApprovalService,
    KnowledgeCaptureService,
    KnowledgeGapDetectionService,
    KnowledgeGapDetector,
)
from blend_brain.knowledge_lifecycle.infrastructure import (
    SnowflakeKnowledgeLifecycleRepository,
    UtcClock,
    Uuid4Generator,
)

if TYPE_CHECKING:
    from blend_brain.knowledge_lifecycle.infrastructure.snowflake import ConnectionFactory


@dataclass(frozen=True, slots=True)
class KnowledgeLifecycleServices:
    """Phase 7 services exposed only to trusted orchestration layers."""

    gap_detection: KnowledgeGapDetectionService
    capture: KnowledgeCaptureService
    approval: KnowledgeApprovalService


def create_knowledge_lifecycle_services(settings: Settings) -> KnowledgeLifecycleServices:
    """Build Phase 7 services from validated Snowflake configuration."""
    if not settings.snowflake_enabled:
        raise ValueError("BLEND_BRAIN_SNOWFLAKE_ENABLED must be true for Phase 7")
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
        query_tag="blend-knowledge-brain:phase-7",
    )
    connection_factory = cast("ConnectionFactory", SnowflakeConnectionFactory(config))
    repository = SnowflakeKnowledgeLifecycleRepository(
        connection_factory,
        database=config.database,
        schema=config.schema,
    )
    clock = UtcClock()
    identifiers = Uuid4Generator()
    limits = CaptureLimits(
        max_value_characters=settings.knowledge_max_value_characters,
        max_rationale_characters=settings.knowledge_max_rationale_characters,
        max_source_reference_characters=settings.knowledge_max_source_reference_characters,
    )
    return KnowledgeLifecycleServices(
        gap_detection=KnowledgeGapDetectionService(KnowledgeGapDetector(), repository, clock),
        capture=KnowledgeCaptureService(repository, clock, identifiers, limits),
        approval=KnowledgeApprovalService(
            repository,
            clock,
            identifiers,
            max_reason_characters=settings.knowledge_max_rationale_characters,
        ),
    )
