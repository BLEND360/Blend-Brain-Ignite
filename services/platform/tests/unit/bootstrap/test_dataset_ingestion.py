"""Local dataset-ingestion command tests."""

from pathlib import Path

import pytest

from blend_brain.bootstrap.dataset_ingestion import project_id_for


def test_project_id_is_stable_and_dataset_relative(tmp_path: Path) -> None:
    root = tmp_path / "dataset"
    nested = root / "Client" / "Case Study.pptx"
    nested.parent.mkdir(parents=True)
    nested.touch()

    first = project_id_for(root, nested)
    second = project_id_for(root, nested)

    assert first == second
    assert first.startswith("pih-")

    with pytest.raises(ValueError, match="not in the subpath"):
        project_id_for(root, tmp_path / "outside.pptx")
