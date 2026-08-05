"""
Build job_id mapping: silver hash IDs -> big-company JOBxxxxx IDs.
Match by content hash of (title + company).
Apply mapping to gold labels to produce evaluation-ready labels.

Usage: python scripts/build_job_id_mapping.py
"""

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SILVER_PATH = REPO_ROOT / "dataset" / "incoming" / "resume_job_silver_30.jsonl"
JOBS_PATH = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "jobs.jsonl"
GOLD_LABELS = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "label_pairs_gold.jsonl"
OUTPUT_MAPPING = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "job_id_mapping.json"
OUTPUT_GOLD_FIXED = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "label_pairs_gold_fixed.jsonl"


def content_key(title: str) -> str:
    return hashlib.sha256(title.encode("utf-8")).hexdigest()


def main():
    print("=" * 60)
    print("Building job_id mapping")

    # 1. Silver jobs: key -> hash_id
    print("\n1. Silver jobs...")
    silver_keys = {}
    with open(SILVER_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            jid = r.get("job_id", "")
            k = content_key(r.get("job_title", ""))
            if jid and k:
                silver_keys[k] = jid
    print(f"   {len(silver_keys)} jobs")

    # 2. Big-company jobs: key -> JOBxxxxx
    print("2. Big-company jobs...")
    big_keys = {}
    with open(JOBS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            jid = r.get("job_id", "")
            k = content_key(r.get("title", ""))
            if jid and k:
                big_keys[k] = jid
    print(f"   {len(big_keys)} jobs")

    # 3. Match
    mapping = {}
    for k, hash_id in silver_keys.items():
        if k in big_keys:
            mapping[hash_id] = big_keys[k]
    print(f"3. Matched: {len(mapping)} / {len(silver_keys)}")

    if len(mapping) == 0:
        print("FAILED: zero matches")
        sys.exit(1)

    OUTPUT_MAPPING.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_MAPPING, "w", encoding="utf-8") as f:
        json.dump({"matched": len(mapping), "mapping": mapping}, f, ensure_ascii=False, indent=2)
    print(f"   -> {OUTPUT_MAPPING}")

    # 4. Translate gold labels
    translated = 0
    with open(GOLD_LABELS, "r", encoding="utf-8") as f_in, \
         open(OUTPUT_GOLD_FIXED, "w", encoding="utf-8") as f_out:
        for line in f_in:
            if not line.strip():
                continue
            r = json.loads(line)
            old = r.get("job_id", "")
            if old in mapping:
                r["job_id"] = mapping[old]
                r["pair_key"] = f"{r.get('candidate_id', '')}::{mapping[old]}"
                translated += 1
            f_out.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(f"4. Gold labels translated: {translated}")
    print(f"   -> {OUTPUT_GOLD_FIXED}")
    print("\nDone!")


if __name__ == "__main__":
    main()
