"""Safe local filesystem storage for generated PDF exports."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath

from blend_brain.business_artifacts.application.ports import StoredObject
from blend_brain.business_artifacts.domain import ArtifactExportError


class LocalArtifactObjectStore:
    """Persist private artifacts beneath one configured local directory."""

    def __init__(self, root_directory: str | Path) -> None:
        if not str(root_directory).strip():
            raise ValueError("Local artifact export directory cannot be empty")
        self._root = Path(root_directory).expanduser().resolve()
        if self._root.exists() and not self._root.is_dir():
            raise ArtifactExportError("Local artifact export location is not a directory")
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as exception:
            raise ArtifactExportError(
                "Local artifact export directory could not be created"
            ) from exception

    def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        """Atomically store bytes in a private local file."""
        if not content_type.strip():
            raise ArtifactExportError("Artifact content type cannot be empty", object_key=key)
        target = self._target_for(key)
        temporary_path: Path | None = None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_path.chmod(0o600)
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(target)
        except OSError as exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ArtifactExportError("Local PDF storage failed", object_key=key) from exception
        return StoredObject(storage_location=str(self._root), key=key)

    def delete(self, key: str) -> None:
        """Delete an orphaned export during compensating cleanup."""
        target = self._target_for(key)
        try:
            target.unlink(missing_ok=True)
        except OSError as exception:
            raise ArtifactExportError("Local PDF cleanup failed", object_key=key) from exception

    def _target_for(self, key: str) -> Path:
        """Resolve an object key while preventing absolute paths and traversal."""
        normalized = key.strip().replace("\\", "/")
        relative_path = PurePosixPath(normalized)
        if (
            not normalized
            or relative_path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative_path.parts)
        ):
            raise ArtifactExportError("Artifact object key is invalid", object_key=key)
        target = self._root.joinpath(*relative_path.parts).resolve()
        if not target.is_relative_to(self._root):
            raise ArtifactExportError("Artifact object key escapes storage root", object_key=key)
        return target
