"""Run a large offline role-level evaluation over all candidate profiles.

This evaluates the same role-aware two-stage contract as the 100-case evaluator:
learn role-discriminating skill weights from train profiles, choose a canonical
role, then rank concrete JDs only inside that role. The full profile pool has
source role labels but no per-profile human-approved JD label, so this script
does not report an invented JD accuracy.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluate_canonical_matching_two_stage import (
    DEFAULT_JOBS,
    DEFAULT_PROFILES,
    DEFAULT_ROLE_MAP,
    build_role_classifier,
    read_csv,
    read_jsonl,
    score_job,
    skill_set,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "canonical_matching_eval_full_profiles_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rank_profile_fast(
    candidate_skills: set[str],
    jobs_by_role: dict[str, list[dict[str, Any]]],
    role_names: dict[str, str],
    role_weights: dict[str, dict[str, float]],
    top_k: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Choose the role from learned weights, then score only that role's JDs.

    With learned weights this is equivalent to the production adapter's role
    ordering: the classifier score is the primary key and JD aggregation is a
    tie-breaker. Restricting JD scoring to the selected role makes 30k-profile
    evaluation practical without changing the decision rule.
    """
    role_rows: list[dict[str, Any]] = []
    for role_id in sorted(set(jobs_by_role) | set(role_weights)):
        weights = role_weights.get(role_id, {})
        classifier_score = sum(max(0.0, weights.get(skill, 0.0)) for skill in candidate_skills)
        role_rows.append({
            "canonical_role_id": role_id,
            "canonical_role": role_names.get(role_id, ""),
            "role_classifier_score": classifier_score,
        })
    role_rows.sort(key=lambda row: (-row["role_classifier_score"], row["canonical_role_id"]))
    if not role_rows:
        return [], []

    selected_role_id = role_rows[0]["canonical_role_id"]
    selected_jobs = []
    for job in jobs_by_role.get(selected_role_id, []):
        selected_jobs.append({
            "job_id": str(job.get("job_id") or job.get("id") or ""),
            "job_title": job.get("title", ""),
            "canonical_role_id": selected_role_id,
            "canonical_role": role_names.get(selected_role_id, ""),
            **score_job(candidate_skills, job),
        })
    selected_jobs.sort(key=lambda row: (-row["score"], -row["required_recall"], -row["f1"], row["job_id"]))
    return selected_jobs[:top_k], role_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    return {
        "cases": total,
        "unique_candidates": len({row["candidate_id"] for row in rows}),
        "target_role_known": sum(row["target_role_known"] for row in rows),
        "role_top1_accuracy": round(sum(row["role_hit"] for row in rows) / max(1, total), 6),
        "role_top3_recall": round(sum(row["role_hit_at_3"] for row in rows) / max(1, total), 6),
        "role_top5_recall": round(sum(row["role_hit_at_5"] for row in rows) / max(1, total), 6),
        "nonempty_skill_profiles": sum(row["skill_count"] > 0 for row in rows),
        "zero_skill_profiles": sum(row["skill_count"] == 0 for row in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate all labeled candidate profiles against canonical roles")
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--role-map", type=Path, default=DEFAULT_ROLE_MAP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    jobs = [row for row in read_jsonl(args.jobs) if row.get("role_mapping_status") == "mapped"]
    profiles = read_jsonl(args.profiles)
    role_map = {row["source_standard_job"]: row["role_id"] for row in read_csv(args.role_map)}
    role_weights, train_profiles = build_role_classifier(profiles, role_map)

    jobs_by_role: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    role_names: dict[str, str] = {}
    for job in jobs:
        role_id = str(job.get("canonical_role_id") or "")
        jobs_by_role[role_id].append(job)
        role_names.setdefault(role_id, str(job.get("canonical_role") or ""))

    case_rows: list[dict[str, Any]] = []
    role_confusion: Counter[tuple[str, str]] = Counter()
    for profile in profiles:
        target_source = str(profile.get("target_job_family") or "")
        target_role = role_map.get(target_source, "")
        skills = skill_set(profile.get("skills_normalized") or profile.get("skills"))
        ranked_jobs, ranked_roles = rank_profile_fast(skills, jobs_by_role, role_names, role_weights, args.top_k)
        predicted_role = ranked_roles[0]["canonical_role_id"] if ranked_roles else ""
        top_role_ids = {row["canonical_role_id"] for row in ranked_roles[:5]}
        row = {
            "candidate_id": profile.get("candidate_id", ""),
            "split": profile.get("split", "unknown"),
            "source_target_role": target_source,
            "target_role_id": target_role,
            "target_role_known": bool(target_role),
            "predicted_role_id": predicted_role,
            "predicted_role": role_names.get(predicted_role, ""),
            "role_hit": bool(target_role and predicted_role == target_role),
            "role_hit_at_3": bool(target_role and target_role in {r["canonical_role_id"] for r in ranked_roles[:3]}),
            "role_hit_at_5": bool(target_role and target_role in top_role_ids),
            "skill_count": len(skills),
            "predicted_job_id": ranked_jobs[0]["job_id"] if ranked_jobs else "",
            "predicted_job_title": ranked_jobs[0]["job_title"] if ranked_jobs else "",
            "predicted_job_score": round(float(ranked_jobs[0]["score"]), 6) if ranked_jobs else 0.0,
        }
        case_rows.append(row)
        role_confusion[(target_role, predicted_role)] += 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "profile_metrics.csv", case_rows)

    by_split = {
        split: summarize([row for row in case_rows if row["split"] == split])
        for split in sorted({row["split"] for row in case_rows})
    }
    by_role: list[dict[str, Any]] = []
    for role_id, count in sorted(Counter(row["target_role_id"] for row in case_rows).items()):
        subset = [row for row in case_rows if row["target_role_id"] == role_id]
        metrics = summarize(subset)
        by_role.append({
            "target_role_id": role_id,
            "target_role": role_names.get(role_id, ""),
            "source_profile_count": count,
            **metrics,
        })
    write_csv(args.output_dir / "metrics_by_role.csv", by_role)
    confusion_rows = [
        {"target_role_id": target, "predicted_role_id": predicted, "count": count}
        for (target, predicted), count in role_confusion.most_common()
    ]
    write_csv(args.output_dir / "role_confusion.csv", confusion_rows)

    manifest = {
        "version": "canonical_matching_eval_full_profiles_v1",
        "algorithm": "train-profile skill log-odds role selection -> concrete JD scoring inside selected canonical role",
        "input_jobs": str(args.jobs),
        "input_profiles": str(args.profiles),
        "input_role_map": str(args.role_map),
        "job_count": len(jobs),
        "canonical_role_count": len(jobs_by_role),
        "profile_count": len(profiles),
        "training_profiles": train_profiles,
        "metrics_all": summarize(case_rows),
        "metrics_by_split": by_split,
        "label_scope": "All profiles have source target_job_family labels mapped to canonical roles; no per-profile human-approved concrete JD label is present.",
        "interpretation": "Role metrics are closed-set offline agreement with the profile source labels. Train metrics are in-sample; dev/test are held-out within the same generated dataset family. This is not a real-resume end-to-end generalization estimate.",
        "source_hashes": {
            "jobs": sha256(args.jobs),
            "profiles": sha256(args.profiles),
            "role_map": sha256(args.role_map),
        },
        "outputs": {
            "profile_metrics": "profile_metrics.csv",
            "metrics_by_role": "metrics_by_role.csv",
            "role_confusion": "role_confusion.csv",
        },
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
