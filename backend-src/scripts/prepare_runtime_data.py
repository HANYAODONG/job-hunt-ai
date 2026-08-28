"""Prepare packaged runtime datasets before the API starts.

The repository keeps large runtime databases in ZIP archives. This command is
idempotent: it extracts an archive only when its required output is missing.
"""

from __future__ import annotations

from pathlib import Path
from shutil import copyfileobj
from typing import Iterable
from zipfile import ZipFile


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _safe_extract(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    with ZipFile(archive) as bundle:
        for member in bundle.infolist():
            # Some Windows-created packages store backslashes in ZIP entries.
            relative = Path(*member.filename.replace("\\", "/").split("/"))
            target = (destination / relative).resolve()
            if destination not in target.parents and target != destination:
                raise ValueError(f"Unsafe path in {archive.name}: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as output:
                copyfileobj(source, output)


def _extract_if_missing(
    archive: Path,
    destination: Path,
    required: Path | Iterable[Path],
) -> bool:
    required_files = [required] if isinstance(required, Path) else list(required)
    if required_files and all(path.exists() for path in required_files):
        print(f"[runtime-data] ready: {', '.join(map(str, required_files))}", flush=True)
        return False
    if not archive.exists():
        print(f"[runtime-data] package not found, skipping: {archive}", flush=True)
        return False
    destination.mkdir(parents=True, exist_ok=True)
    print(f"[runtime-data] extracting {archive.name} -> {destination}", flush=True)
    _safe_extract(archive, destination)
    missing = [path for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError(
            f"Package {archive} did not provide required runtime files: {missing}"
        )
    return True


def prepare_runtime_data() -> None:
    company_dir = (
        BACKEND_ROOT
        / "job_update"
        / "company_job_update"
        / "data"
        / "versions"
        / "company_large_v2"
    )
    _extract_if_missing(
        company_dir / "job_update_company_runtime_data.zip",
        company_dir,
        company_dir / "job_update.db",
    )

    government_root = BACKEND_ROOT / "job_update" / "government_job_update"
    _extract_if_missing(
        government_root / "job_update_government_runtime_data.zip",
        government_root,
        government_root / "data" / "base" / "government_job_update.db",
    )

    artifact_roots = [BACKEND_ROOT / "artifacts", BACKEND_ROOT.parent / "artifacts"]
    artifact_root = next((path for path in artifact_roots if path.exists()), artifact_roots[0])
    _extract_if_missing(
        artifact_root / "workflow1_dataset_iteration_05.zip",
        artifact_root,
        (
            artifact_root / "dataset_iteration_05" / "dataset_manifest.json",
            artifact_root / "dataset_iteration_05" / "jobs.jsonl",
            artifact_root / "dataset_iteration_05" / "candidate_profiles.jsonl",
        ),
    )
    _extract_if_missing(
        artifact_root / "semantic_index_runtime.zip",
        artifact_root,
        (
            artifact_root / "semantic_index" / "jobs_embeddings.npy",
            artifact_root / "semantic_index" / "jobs_embedding_ids.json",
            artifact_root / "semantic_index" / "model_metadata.json",
        ),
    )


if __name__ == "__main__":
    prepare_runtime_data()
