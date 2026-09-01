"""Evaluate two-stage resume-to-job matching on the canonical JD pool.

The matcher intentionally does not use the case's target role as an input. It
scores every mapped JD from resume skills, aggregates scores by canonical role,
then selects the best concrete JD inside the best role. The expert annotation
pack is used only for evaluation labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from canonical_job_title import canonical_job_title


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current" / "canonical_jobs.jsonl"
DEFAULT_PACK = REPO_ROOT / "artifacts" / "canonical_matching_review_v1_100"
DEFAULT_PROFILES = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "candidate_profiles.jsonl"
DEFAULT_ROLE_MAP = REPO_ROOT / "backend-src" / "app" / "data" / "canonical_role_pool" / "v1" / "source_role_mapping.csv"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "canonical_matching_eval_v1"


# These aliases only normalize common surface forms. They do not encode the
# answer role and therefore cannot leak the gold label into ranking.
SKILL_ALIASES = {
    "golang": "go",
    "go语言": "go",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "python3": "python",
    "py": "python",
    "c++": "c/c++",
    "cpp": "c/c++",
    "c／c++": "c/c++",
    "大语言模型": "大模型",
    "large language model": "大模型",
    "llm": "大模型",
    "machine learning": "机器学习",
    "deep learning": "深度学习",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_role_classifier(profiles: list[dict[str, Any]], role_map: dict[str, str]) -> tuple[dict[str, dict[str, float]], int]:
    """Learn role-distinguishing skill weights from training profiles only."""
    role_counts: defaultdict[str, int] = defaultdict(int)
    role_skill_counts: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    skill_counts: defaultdict[str, int] = defaultdict(int)
    train_count = 0
    for profile in profiles:
        if profile.get("split") != "train":
            continue
        role_id = role_map.get(str(profile.get("target_job_family") or ""))
        if not role_id:
            continue
        train_count += 1
        role_counts[role_id] += 1
        skills = skill_set(profile.get("skills_normalized") or profile.get("skills"))
        for skill in skills:
            role_skill_counts[role_id][skill] += 1
            skill_counts[skill] += 1

    total = sum(role_counts.values())
    weights: dict[str, dict[str, float]] = {}
    for role_id, counts in role_skill_counts.items():
        role_total = role_counts[role_id]
        role_weights: dict[str, float] = {}
        for skill, total_count in skill_counts.items():
            role_rate = (counts.get(skill, 0) + 1) / (role_total + 2)
            other_rate = (total_count - counts.get(skill, 0) + 1) / (total - role_total + 2)
            role_weights[skill] = math.log(role_rate / other_rate)
        weights[role_id] = role_weights
    return weights, train_count


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_skill(value: Any) -> str:
    text = str(value or "").strip().casefold()
    return SKILL_ALIASES.get(text, text)


def skill_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {normalize_skill(value) for value in values if normalize_skill(value)}


def score_job(candidate_skills: set[str], job: dict[str, Any]) -> dict[str, Any]:
    required = skill_set(job.get("required_skills") or job.get("skills"))
    preferred = skill_set(job.get("preferred_skills"))
    shared_required = candidate_skills & required
    shared_preferred = candidate_skills & preferred
    if required:
        recall = len(shared_required) / len(required)
    else:
        recall = 0.0
    precision = len(shared_required) / len(candidate_skills) if candidate_skills else 0.0
    f1 = (2 * recall * precision / (recall + precision)) if recall + precision else 0.0
    preferred_bonus = min(1.0, len(shared_preferred) / max(1, len(preferred))) if preferred else 0.0
    # Recall is dominant because missing a must-have skill is more serious
    # than having additional transferable skills.
    score = 0.60 * recall + 0.25 * f1 + 0.10 * precision + 0.05 * preferred_bonus
    return {
        "score": score,
        "required_recall": recall,
        "candidate_precision": precision,
        "f1": f1,
        "shared_required": sorted(shared_required),
        "shared_preferred": sorted(shared_preferred),
    }


def rank_case(
    candidate_skills: set[str],
    jobs: list[dict[str, Any]],
    top_k: int,
    role_weights: dict[str, dict[str, float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scored: list[dict[str, Any]] = []
    for job in jobs:
        metrics = score_job(candidate_skills, job)
        scored.append({
            "job_id": str(job.get("job_id") or job.get("id") or ""),
            "job_title": job.get("title", ""),
            "canonical_role_id": str(job.get("canonical_role_id") or ""),
            "canonical_role": job.get("canonical_role", ""),
            "job_title_label": canonical_job_title(job),
            **metrics,
        })
    scored.sort(key=lambda row: (-row["score"], -row["required_recall"], -row["f1"], row["job_id"]))

    by_role: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        by_role[row["canonical_role_id"]].append(row)
    role_rows: list[dict[str, Any]] = []
    for role_id, rows in by_role.items():
        top = rows[:3]
        # Max captures the best concrete opportunity; the smaller mean term
        # prevents a role from winning on one accidental skill-only JD.
        role_score = 0.70 * top[0]["score"] + 0.30 * sum(row["score"] for row in top) / len(top)
        classifier_score = sum(max(0.0, role_weights.get(role_id, {}).get(skill, 0.0)) for skill in candidate_skills)
        role_rows.append({
            "canonical_role_id": role_id,
            "canonical_role": top[0]["canonical_role"],
            "role_score": role_score,
            "role_classifier_score": classifier_score,
            "best_job_id": top[0]["job_id"],
            "best_job_title": top[0]["job_title"],
            "top_job_ids": [row["job_id"] for row in top],
        })
    if role_weights:
        role_rows.sort(key=lambda row: (-row["role_classifier_score"], -row["role_score"], row["canonical_role_id"]))
    else:
        role_rows.sort(key=lambda row: (-row["role_score"], row["canonical_role_id"]))
    # Stage two is explicitly constrained to the stage-one winning role.
    selected_role_id = role_rows[0]["canonical_role_id"] if role_rows else ""
    selected_role_jobs = [row for row in scored if row["canonical_role_id"] == selected_role_id]
    return selected_role_jobs[:top_k], role_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate two-stage canonical resume/job matching")
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--role-map", type=Path, default=DEFAULT_ROLE_MAP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    jobs = [row for row in read_jsonl(args.jobs) if row.get("role_mapping_status") == "mapped"]
    profiles = read_jsonl(args.profiles)
    role_map = {row["source_standard_job"]: row["role_id"] for row in read_csv(args.role_map)}
    role_weights, train_profiles = build_role_classifier(profiles, role_map)
    cases = read_csv(args.pack_dir / "expert_gpt_cases.csv")
    options = read_csv(args.pack_dir / "expert_gpt_annotations.csv")
    accepted_by_case = {
        row["case_id"]: set(json.loads(row.get("gold_accepted_job_ids") or "[]"))
        for row in cases
    }
    accepted_titles_by_case = {
        row["case_id"]: set(json.loads(row.get("gold_accepted_title_labels") or "[]"))
        for row in cases
    }
    role_by_case = {row["case_id"]: row.get("gold_canonical_role_id", "") for row in cases}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ranking_rows: list[dict[str, Any]] = []
    role_rows_out: list[dict[str, Any]] = []
    case_metrics: list[dict[str, Any]] = []
    for case in cases:
        try:
            candidate_skills = skill_set(json.loads(case.get("candidate_skills") or "[]"))
        except json.JSONDecodeError:
            candidate_skills = set()
        ranked_jobs, ranked_roles = rank_case(candidate_skills, jobs, args.top_k, role_weights)
        case_id = case["case_id"]
        accepted = accepted_by_case.get(case_id, set())
        target_role = role_by_case.get(case_id, "")
        top_job = ranked_jobs[0] if ranked_jobs else {}
        top_role = ranked_roles[0] if ranked_roles else {}
        option_rows = [row for row in options if row["case_id"] == case_id]
        known_title_labels = {str(row.get("job_title_label") or "") for row in option_rows}
        predicted_title_label = str(top_job.get("job_title_label") or "")
        known_top1 = predicted_title_label in known_title_labels
        top_k_ids = {row["job_id"] for row in ranked_jobs}
        top_1_ids = {row["job_id"] for row in ranked_jobs[:1]}
        top_2_ids = {row["job_id"] for row in ranked_jobs[:2]}
        top_3_ids = {row["job_id"] for row in ranked_jobs[:3]}
        top_5_ids = {row["job_id"] for row in ranked_jobs[:5]}
        top_k_title_labels = {str(row.get("job_title_label") or "") for row in ranked_jobs}
        case_metrics.append({
            "case_id": case_id,
            "candidate_id": case["candidate_id"],
            "target_role_id": target_role,
            "predicted_role_id": top_role.get("canonical_role_id", ""),
            "predicted_job_id": top_job.get("job_id", ""),
            "predicted_job_title_label": predicted_title_label,
            "role_hit": top_role.get("canonical_role_id") == target_role,
            "role_hit_at_3": target_role in {row["canonical_role_id"] for row in ranked_roles[:3]},
            "role_hit_at_5": target_role in {row["canonical_role_id"] for row in ranked_roles[:5]},
            "strict_jd_hit": top_job.get("job_id") in accepted,
            "title_label_hit": predicted_title_label in accepted_titles_by_case.get(case_id, set()),
            "title_label_hit_at_10": bool(top_k_title_labels & accepted_titles_by_case.get(case_id, set())),
            "role_and_title_hit": (
                top_role.get("canonical_role_id") == target_role
                and predicted_title_label in accepted_titles_by_case.get(case_id, set())
            ),
            "top_k_accepted_hit": bool(top_k_ids & accepted),
            "accepted_jd_hit_at_1": bool(top_1_ids & accepted),
            "accepted_jd_hit_at_2": bool(top_2_ids & accepted),
            "accepted_jd_hit_at_3": bool(top_3_ids & accepted),
            "accepted_jd_hit_at_5": bool(top_5_ids & accepted),
            "strict_jd_label_status": "known" if known_top1 else "unlabeled",
            "accepted_job_ids": json.dumps(sorted(accepted), ensure_ascii=False),
            "predicted_role_score": round(float(top_role.get("role_score", 0.0)), 6),
            "predicted_job_score": round(float(top_job.get("score", 0.0)), 6),
        })
        for rank, row in enumerate(ranked_jobs, start=1):
            ranking_rows.append({"case_id": case_id, "rank": rank, **row})
        for rank, row in enumerate(ranked_roles, start=1):
            role_rows_out.append({"case_id": case_id, "rank": rank, **row})

    total = len(case_metrics)
    known_cases = [row for row in case_metrics if row["strict_jd_label_status"] == "known"]
    metrics = {
        "cases": total,
        "unique_candidates": len({row["candidate_id"] for row in case_metrics}),
        "mapped_jobs_scored_per_case": len(jobs),
        "role_top1_accuracy": round(sum(row["role_hit"] for row in case_metrics) / max(1, total), 6),
        "role_top3_recall": round(sum(row["role_hit_at_3"] for row in case_metrics) / max(1, total), 6),
        "role_top5_recall": round(sum(row["role_hit_at_5"] for row in case_metrics) / max(1, total), 6),
        "strict_jd_top1_known_label_accuracy": round(sum(row["strict_jd_hit"] for row in known_cases) / max(1, len(known_cases)), 6),
        "strict_jd_top1_known_label_cases": len(known_cases),
        "strict_jd_top1_unlabeled_cases": total - len(known_cases),
        "accepted_jd_recall_at_1": round(sum(row["accepted_jd_hit_at_1"] for row in case_metrics) / max(1, total), 6),
        "accepted_jd_recall_at_2": round(sum(row["accepted_jd_hit_at_2"] for row in case_metrics) / max(1, total), 6),
        "accepted_jd_recall_at_3": round(sum(row["accepted_jd_hit_at_3"] for row in case_metrics) / max(1, total), 6),
        "accepted_jd_recall_at_5": round(sum(row["accepted_jd_hit_at_5"] for row in case_metrics) / max(1, total), 6),
        "accepted_jd_recall_at_10": round(sum(row["top_k_accepted_hit"] for row in case_metrics) / max(1, total), 6),
        "normalized_title_top1_accuracy": round(sum(row["title_label_hit"] for row in case_metrics) / max(1, total), 6),
        "normalized_title_recall_at_10": round(sum(row["title_label_hit_at_10"] for row in case_metrics) / max(1, total), 6),
        "role_and_normalized_title_top1_accuracy": round(sum(row["role_and_title_hit"] for row in case_metrics) / max(1, total), 6),
        "note": "Primary labels are normalized closed-set job title labels. Exact job_id metrics are secondary evidence metrics because multiple JD records can share one accepted title label.",
        "generalization_warning": "The current 100 cases and training profiles are generated from the same synthetic dataset family; results are a pipeline sanity check, not a real-resume generalization estimate.",
    }

    def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        fields = list(rows[0]) if rows else []
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    write_csv(args.output_dir / "case_metrics.csv", case_metrics)
    write_csv(args.output_dir / "job_rankings_topk.csv", ranking_rows)
    write_csv(args.output_dir / "role_rankings.csv", role_rows_out)
    manifest = {
        "version": "canonical_matching_eval_v1",
        "algorithm": "training-profile role classifier -> full-pool JD scoring inside predicted canonical role -> concrete JD ranking",
        "input_jobs": str(args.jobs),
        "input_review_pack": str(args.pack_dir),
        "job_count": len(jobs),
        "training_profiles": train_profiles,
        "role_classifier": "training-profile skill log-odds" if role_weights else "unavailable; JD role aggregation fallback",
        "top_k": args.top_k,
        "evaluation_protocol": {
            "unit_of_evaluation": "resume_case",
            "case_count": total,
            "role_stage": "select canonical third-level role first",
            "jd_stage": "rank concrete JD only inside selected canonical role",
            "primary_jd_metrics": ["accepted_jd_recall_at_2", "accepted_jd_recall_at_3"],
            "strict_secondary_metric": "accepted_jd_recall_at_1",
            "why_recall_at_k": "Multiple concrete JD records can be acceptable for the same resume and canonical role; a hit is counted when any accepted JD appears in the first K results.",
            "docker_used": False,
            "core_algorithm_changed": False,
        },
        "metrics": metrics,
        "source_hashes": {
            "jobs": sha256(args.jobs),
            "profiles": sha256(args.profiles),
            "role_map": sha256(args.role_map),
            "expert_cases": sha256(args.pack_dir / "expert_gpt_cases.csv"),
            "expert_annotations": sha256(args.pack_dir / "expert_gpt_annotations.csv"),
        },
        "outputs": {
            "case_metrics": "case_metrics.csv",
            "job_rankings_topk": "job_rankings_topk.csv",
            "role_rankings": "role_rankings.csv",
        },
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
