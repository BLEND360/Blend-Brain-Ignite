"""Command-line composition for resumable local dataset ingestion."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from blend_brain.bootstrap.configuration import Settings
from blend_brain.bootstrap.enrichment import create_knowledge_enrichment_service
from blend_brain.document_ingestion.infrastructure import (
    FileSystemDocumentScanner,
    create_local_ingestion_service,
)
from blend_brain.knowledge_enrichment.application import (
    BatchDocument,
    BatchResult,
    DatasetIngestionService,
)
from blend_brain.knowledge_enrichment.infrastructure import (
    SnowflakeConnectionFactory,
    SnowflakeKnowledgeRepository,
)
from blend_brain.knowledge_enrichment.infrastructure.snowflake import SnowflakeConnectionConfig


def project_id_for(root: Path, source: Path) -> str:
    """Return a stable opaque project ID for one dataset-relative source path."""
    relative = source.resolve().relative_to(root.resolve()).as_posix().casefold()
    return f"pih-{uuid5(NAMESPACE_URL, f'blend-brain:pih:{relative}')}"


def main(arguments: list[str] | None = None) -> int:
    """Scan, enrich, persist, and report one local dataset batch."""
    options = _parser().parse_args(arguments)
    root = options.dataset_root.expanduser().resolve()
    paths = FileSystemDocumentScanner().discover(root)
    if options.limit is not None:
        paths = paths[: options.limit]
    settings = Settings()
    enrichment = create_knowledge_enrichment_service(settings)
    repository = _repository(settings)
    documents = tuple(
        BatchDocument(str(path.resolve()), project_id_for(root, path)) for path in paths
    )
    service = DatasetIngestionService(create_local_ingestion_service(), enrichment)
    result = service.run(
        documents,
        completed_document_ids=repository.completed_document_ids(),
        max_workers=options.workers,
        progress=_write_progress,
    )
    _write_report(options.report.expanduser().resolve(), result)
    sys.stdout.write(
        f"summary discovered={result.discovered} completed={result.completed} "
        f"skipped={result.skipped} failed={len(result.failures)}\n"
    )
    return 1 if result.failures else 0


def _repository(settings: Settings) -> SnowflakeKnowledgeRepository:
    """Build the status reader with the same configuration as enrichment persistence."""
    required = (
        settings.snowflake_account,
        settings.snowflake_user,
        settings.snowflake_warehouse,
        settings.snowflake_database,
    )
    if not settings.snowflake_enabled or not all(required):
        raise ValueError("Complete enabled Snowflake settings are required")
    config = SnowflakeConnectionConfig(
        account=settings.snowflake_account or "",
        user=settings.snowflake_user or "",
        warehouse=settings.snowflake_warehouse or "",
        database=settings.snowflake_database or "",
        schema=settings.snowflake_schema,
        role=settings.snowflake_role,
        password=settings.snowflake_password.get_secret_value()
        if settings.snowflake_password
        else None,
        private_key_file=settings.snowflake_private_key_file,
        private_key_file_password=settings.snowflake_private_key_file_password.get_secret_value()
        if settings.snowflake_private_key_file_password
        else None,
        query_tag="blend-knowledge-brain:dataset-ingestion",
    )
    return SnowflakeKnowledgeRepository(
        SnowflakeConnectionFactory(config),
        database=config.database,
        schema=config.schema,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest a local Blend Brain dataset")
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--limit", type=_positive_int)
    parser.add_argument("--workers", type=_positive_int, default=1)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(".local/ingestion-report.json"),
    )
    return parser


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("limit must be greater than zero")
    return parsed


def _write_progress(index: int, total: int, status: str, document: BatchDocument) -> None:
    sys.stdout.write(f"[{index}/{total}] {status} {Path(document.source_id).name}\n")
    sys.stdout.flush()


def _write_report(path: Path, result: BatchResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(result), indent=2, sort_keys=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(payload)
            temporary_file.flush()
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
