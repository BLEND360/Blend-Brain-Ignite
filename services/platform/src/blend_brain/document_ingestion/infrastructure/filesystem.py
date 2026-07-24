"""Bounded and deterministic local-filesystem source adapters."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from blend_brain.document_ingestion.domain import (
    DocumentAccessError,
    DocumentSource,
    DocumentTooLargeError,
)

SUPPORTED_SUFFIXES = frozenset({".pptx", ".docx", ".pdf", ".md", ".markdown", ".txt"})


@dataclass(frozen=True, slots=True)
class IngestionLimits:
    """Resource ceilings applied before untrusted documents reach parsers."""

    max_file_size_bytes: int = 100 * 1024 * 1024
    max_archive_entries: int = 10_000
    max_archive_uncompressed_bytes: int = 500 * 1024 * 1024
    max_archive_compression_ratio: float = 100.0
    max_pdf_pages: int = 2_000

    def __post_init__(self) -> None:
        for name in (
            "max_file_size_bytes",
            "max_archive_entries",
            "max_archive_uncompressed_bytes",
            "max_pdf_pages",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.max_archive_compression_ratio < 1:
            raise ValueError("max_archive_compression_ratio must be at least one")


class FileSystemSourceLoader:
    """Load regular files without following symbolic links."""

    def __init__(self, limits: IngestionLimits | None = None) -> None:
        self._limits = limits or IngestionLimits()

    def load(self, source_id: str) -> DocumentSource:
        """Read, bound, and fingerprint a local document."""
        path = Path(source_id)
        try:
            is_symlink = path.is_symlink()
            stat = path.stat()
        except OSError as exception:
            raise DocumentAccessError(
                "Document cannot be accessed", source_id=source_id
            ) from exception

        if is_symlink:
            raise DocumentAccessError("Symbolic links are not accepted", source_id=source_id)

        if not path.is_file():
            raise DocumentAccessError("Document source is not a regular file", source_id=source_id)
        if stat.st_size > self._limits.max_file_size_bytes:
            raise DocumentTooLargeError(
                "Document exceeds the configured file-size limit",
                source_id=source_id,
                size_bytes=stat.st_size,
                limit_bytes=self._limits.max_file_size_bytes,
            )

        try:
            content = path.read_bytes()
        except OSError as exception:
            raise DocumentAccessError("Document cannot be read", source_id=source_id) from exception
        if len(content) > self._limits.max_file_size_bytes:
            raise DocumentTooLargeError(
                "Document grew beyond the configured file-size limit while reading",
                source_id=source_id,
                size_bytes=len(content),
                limit_bytes=self._limits.max_file_size_bytes,
            )

        return DocumentSource(
            source_id=source_id,
            filename=path.name,
            content=content,
            size_bytes=len(content),
            sha256=sha256(content).hexdigest(),
        )


class FileSystemDocumentScanner:
    """Discover supported regular files in stable path order."""

    def __init__(self, *, include_hidden: bool = False) -> None:
        self._include_hidden = include_hidden

    def discover(self, root: Path) -> tuple[Path, ...]:
        """Return supported files below a root without following symlinks."""
        if not root.exists() or not root.is_dir():
            raise DocumentAccessError(
                "Scan root is not an accessible directory", source_id=str(root)
            )

        discovered: list[Path] = []
        try:
            candidates = root.rglob("*")
            for path in candidates:
                relative = path.relative_to(root)
                if not self._include_hidden and any(
                    part.startswith(".") for part in relative.parts
                ):
                    continue
                if path.is_symlink() or not path.is_file():
                    continue
                if path.suffix.lower() in SUPPORTED_SUFFIXES:
                    discovered.append(path)
        except OSError as exception:
            raise DocumentAccessError(
                "Scan root cannot be traversed", source_id=str(root)
            ) from exception
        return tuple(sorted(discovered, key=lambda path: path.as_posix().casefold()))
