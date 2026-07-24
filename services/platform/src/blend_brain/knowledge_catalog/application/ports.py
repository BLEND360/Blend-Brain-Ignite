"""Persistence ports for authorized catalog read models."""

from typing import Protocol

from blend_brain.knowledge_catalog.domain import CatalogProject, DashboardSnapshot


class KnowledgeCatalogRepository(Protocol):
    """Read catalog records within an explicit project allowlist."""

    def all_project_ids(self) -> tuple[str, ...]: ...

    def dashboard(self, project_ids: tuple[str, ...]) -> DashboardSnapshot: ...

    def project(self, project_id: str, project_ids: tuple[str, ...]) -> CatalogProject | None: ...

    def projects(
        self, requested_ids: tuple[str, ...], project_ids: tuple[str, ...]
    ) -> tuple[CatalogProject, ...]: ...
