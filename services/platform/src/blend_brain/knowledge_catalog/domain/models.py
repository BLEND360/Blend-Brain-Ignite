"""Immutable read models used by authenticated catalog queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from blend_brain.knowledge_enrichment.domain import ProjectDNA


@dataclass(frozen=True, slots=True)
class CatalogDocument:
    """An accessible source document attached to a project."""

    document_id: str
    filename: str
    document_format: str
    section_count: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CatalogProject:
    """A project and its current evidence-backed intelligence."""

    project_id: str
    display_name: str
    updated_at: datetime
    dna: ProjectDNA | None
    document_count: int = 0
    documents: tuple[CatalogDocument, ...] = ()
    section_locations: tuple[tuple[int, int | None, int | None, str | None], ...] = ()


@dataclass(frozen=True, slots=True)
class IndustryCount:
    """Project count for one grounded industry classification."""

    name: str
    project_count: int


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Authorized organizational metrics calculated from persisted records."""

    total_projects: int
    indexed_documents: int
    identified_experts: int
    knowledge_coverage: float
    recent_projects: tuple[CatalogProject, ...]
    top_industries: tuple[IndustryCount, ...]
    updated_at: datetime
