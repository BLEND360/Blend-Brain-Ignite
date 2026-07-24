"""Authorization-preserving catalog query orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blend_brain.knowledge_catalog.application.ports import KnowledgeCatalogRepository
    from blend_brain.knowledge_catalog.domain import CatalogProject, DashboardSnapshot


class KnowledgeCatalogService:
    """Expose read models only from the caller's server-established allowlist."""

    def __init__(self, repository: KnowledgeCatalogRepository) -> None:
        self._repository = repository

    def resolve_scope(self, configured_project_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Resolve the local wildcard on the server and discard unknown identifiers."""
        available = self._repository.all_project_ids()
        if configured_project_ids == ("*",):
            return available
        allowed = set(configured_project_ids)
        return tuple(project_id for project_id in available if project_id in allowed)

    def dashboard(self, project_ids: tuple[str, ...]) -> DashboardSnapshot:
        return self._repository.dashboard(self._required_scope(project_ids))

    def project(self, project_id: str, project_ids: tuple[str, ...]) -> CatalogProject | None:
        normalized = project_id.strip()
        if not normalized or normalized not in project_ids:
            return None
        return self._repository.project(normalized, self._required_scope(project_ids))

    def projects(
        self, requested_ids: tuple[str, ...], project_ids: tuple[str, ...]
    ) -> tuple[CatalogProject, ...]:
        scope = self._required_scope(project_ids)
        authorized = tuple(dict.fromkeys(value for value in requested_ids if value in scope))
        return self._repository.projects(authorized, scope) if authorized else ()

    @staticmethod
    def _required_scope(project_ids: tuple[str, ...]) -> tuple[str, ...]:
        if not project_ids:
            raise PermissionError("The authenticated principal has no accessible projects")
        return project_ids
