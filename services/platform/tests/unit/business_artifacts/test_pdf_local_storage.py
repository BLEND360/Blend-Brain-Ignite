"""Real PDF renderer and local artifact-storage tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blend_brain.business_artifacts.domain import (
    ArtifactCitation,
    ArtifactExportError,
    ArtifactSection,
    ArtifactStatement,
)
from blend_brain.business_artifacts.infrastructure.local_filesystem import (
    LocalArtifactObjectStore,
)
from blend_brain.business_artifacts.infrastructure.pdf import ReportLabPdfRenderer
from tests.unit.business_artifacts.helpers import one_pager, proposal

if TYPE_CHECKING:
    from pathlib import Path


def test_reportlab_renders_proposal_and_single_page_one_pager() -> None:
    renderer = ReportLabPdfRenderer()

    proposal_pdf = renderer.render(proposal())
    one_pager_pdf = renderer.render(one_pager())

    assert proposal_pdf.startswith(b"%PDF-")
    assert one_pager_pdf.startswith(b"%PDF-")
    assert len(proposal_pdf) > 1_000


def test_one_pager_rejects_content_that_overflows_one_page() -> None:
    statement = ArtifactStatement(
        "A very long grounded sentence. " * 30,
        (ArtifactCitation("P1", "grounded"),),
    )
    sections = tuple(
        ArtifactSection(f"section-{index}", f"Section {index}", (statement,) * 3)
        for index in range(10)
    )
    with pytest.raises(ArtifactExportError, match="single-page"):
        ReportLabPdfRenderer().render(one_pager(sections=sections))


def test_local_store_writes_atomically_and_deletes(tmp_path: Path) -> None:
    root = tmp_path / "exports"
    store = LocalArtifactObjectStore(root)

    location = store.put("artifact/file.pdf", b"pdf", "application/pdf")

    target = root / "artifact" / "file.pdf"
    assert location.storage_location == str(root.resolve())
    assert target.read_bytes() == b"pdf"
    assert not tuple(root.rglob("*.tmp"))

    store.delete(location.key)
    assert not target.exists()


@pytest.mark.parametrize("key", ["", "../outside.pdf", "/absolute.pdf", "a/../../outside.pdf"])
def test_local_store_rejects_invalid_or_escaping_keys(tmp_path: Path, key: str) -> None:
    store = LocalArtifactObjectStore(tmp_path / "exports")

    with pytest.raises(ArtifactExportError, match="key"):
        store.put(key, b"pdf", "application/pdf")


def test_local_store_rejects_invalid_root_and_content_type(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        LocalArtifactObjectStore(" ")

    file_path = tmp_path / "file"
    file_path.write_text("not a directory")
    with pytest.raises(ArtifactExportError, match="not a directory"):
        LocalArtifactObjectStore(file_path)

    store = LocalArtifactObjectStore(tmp_path / "exports")
    with pytest.raises(ArtifactExportError, match="content type"):
        store.put("artifact.pdf", b"pdf", " ")
