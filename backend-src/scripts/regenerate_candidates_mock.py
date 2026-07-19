#!/usr/bin/env python3
from pathlib import Path
import json
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]

def find_ids_path():
    candidates = [
        REPO_ROOT / "artifacts" / "semantic_index" / "jobs_embedding_ids.json",
        REPO_ROOT / "artifacts" / "semantic_index_sample" / "jobs_embedding_ids.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

def main():
    ids_path = find_ids_path()
    if ids_path is None:
        print("ERROR: jobs_embedding_ids.json not found under artifacts/semantic_index", file=sys.stderr)
        sys.exit(2)

    with ids_path.open('r', encoding='utf-8') as f:
        ids = json.load(f)

    out = {"job_ids": ids}
    out_path = REPO_ROOT / "backend-src" / "candidates_mock.json"
    with out_path.open('w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {out_path}")

if __name__ == '__main__':
    main()
