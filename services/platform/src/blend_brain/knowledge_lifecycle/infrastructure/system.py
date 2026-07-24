"""System adapters for application time and identifiers."""

from datetime import UTC, datetime
from uuid import uuid4


class UtcClock:
    """Production UTC clock."""

    def now(self) -> datetime:
        """Return an aware UTC timestamp."""
        return datetime.now(UTC)


class Uuid4Generator:
    """Cryptographically random UUID identifier generator."""

    def new(self) -> str:
        """Return a canonical UUID string."""
        return str(uuid4())
