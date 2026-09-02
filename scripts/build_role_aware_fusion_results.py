"""Apply the existing role-aware adapter to offline Fusion results.

The script joins JD metadata by job_id because Fusion batch artifacts contain
scores but deliberately omit metadata. It neither changes Fusion scores nor
adds a new ranking model; it materializes the prescribed role-first output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend-src"
sys.path.insert(0, str(BACKEND))

from app.services.canonical_role_pool import CanonicalRolePool  # noqa: E402
from app.services.role_aware_matching_service import rank_role_aware  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=Path, default=ROOT / "artifacts" / "canonical_role_pool_v2" / "canonical_jobs.jsonl")
    parser.add_argument("--fusion", type=Path, default=ROOT / "artifacts" / "role_pool_runtime" / "v2" / "local_rebuild" / "fusion" / "fusion_full.jsonl")
    parser.add_argument("--role-data-dir", type=Path, default=BACKEND / "app" / "data" / "canonical_role_pool" / "v2")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "role_pool_runtime" / "v2" / "local_rebuild" / "role_aware" / "recommendations.jsonl")
    parser.add_argument("--jd-top-k", type=int, default=10)
    parser.add_argument("--role-top-k", type=int, default=1)
    args = parser.parse_args()

    jobs = {str(row.get("job_id") or row.get("id") or ""): row for row in read_jsonl(args.jobs)}
    pool = CanonicalRolePool(data_dir=args.role_data_dir)
    results: list[dict[str, Any]] = []
    for batch in read_jsonl(args.fusion):
        candidates = []
        for item in batch.get("results") or []:
            job = jobs.get(str(item.get("job_id") or ""))
            if job is None:
                continue
            candidates.append({**item, "meta": job})
        ranked = rank_role_aware(candidates, top_k=args.jd_top_k, role_top_k=args.role_top_k, role_pool=pool)
        results.append({"query_id": batch.get("query_id"), **ranked})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in results:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({"queries": len(results), "output": str(args.output), "role_pool_roles": len(pool.roles)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
