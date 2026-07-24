"""Application-facing configuration contracts."""

from typing import Protocol


class ServiceSettings(Protocol):
    """Minimum service identity required outside the composition root."""

    app_name: str
    app_version: str
