"""Evaluate real PDF upload matching with the optional LLM resume parser.

Gold labels are read only after ranking. The LLM sees extracted resume text,
never the accepted JD IDs or gold role.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend-src"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services.llm_resume_parser import LLMResumeParser
from canonical_job_title import canonical_job_title
from evaluate_canonical_matching_two_stage import (
    build_role_classifier,
    rank_case,
    read_csv,
    read_jsonl,
    skill_set,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, default=ROOT / "artifacts/real_upload_matching_pack_v6_100")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/real_upload_matching_eval_llm_v1_100")
    parser.add_argument("--limit", type=int, default=None, help="Evaluate only the first N manifest items.")
    parser.add_argument("--sample-id", type=str, default=None, help="Evaluate one manifest item by sample_id.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((args.pack / "manifest.json").read_text(encoding="utf-8"))["items"]
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit must be at least 1")
        manifest = manifest[: args.limit]
    if args.sample_id:
        manifest = [item for item in manifest if item.get("sample_id") == args.sample_id]
        if not manifest:
            parser.error(f"sample_id not found: {args.sample_id}")
    profiles = read_jsonl(ROOT / "artifacts/dataset_iteration_05/candidate_profiles.jsonl")
    jobs = [
        row
        for row in read_jsonl(ROOT / "artifacts/canonical_role_pool_v2/canonical_jobs.jsonl")
        if row.get("role_mapping_status") == "mapped"
    ]
    role_map = {
        row["source_standard_job"]: row["role_id"]
        for row in read_csv(ROOT / "backend-src/app/data/canonical_role_pool/v1/source_role_mapping.csv")
    }
    role_weights, training_profiles = build_role_classifier(profiles, role_map)
    jobs_by_id = {str(row.get("job_id") or row.get("id") or ""): row for row in jobs}
    llm_parser = LLMResumeParser()
    rows = []
    started = time.perf_counter()

    for index, item in enumerate(manifest, start=1):
        case_started = time.perf_counter()
        document = fitz.open(str(args.pack / item["pdf"]))
        resume_text = "\n".join(page.get_text("text") for page in document)
        document.close()
        parse_started = time.perf_counter()
        parsed = llm_parser.parse(resume_text)
        parse_ms = (time.perf_counter() - parse_started) * 1000
        candidate_skills = skill_set(parsed.get("skills"))
        ranked, roles = rank_case(candidate_skills, jobs, 10, role_weights)
        predicted_role = roles[0]["canonical_role_id"] if roles else ""
        accepted_ids = set(item.get("accepted_jd_ids") or [])
        accepted_titles = {
            canonical_job_title(jobs_by_id[job_id])
            for job_id in accepted_ids
            if job_id in jobs_by_id
        }
        title_hits = [
            any(canonical_job_title(jobs_by_id.get(row["job_id"], row)) in accepted_titles for row in ranked[:k])
            for k in (1, 2, 3)
        ]
        id_hits = [any(row["job_id"] in accepted_ids for row in ranked[:k]) for k in (1, 2, 3)]
        rows.append(
            {
                "sample_id": item["sample_id"],
                "candidate_id": item["candidate_id"],
                "gold_role": item["gold_role"],
                "predicted_role": predicted_role,
                "role_hit": predicted_role == item["gold_role"],
                "jd_hit_at_1": id_hits[0],
                "jd_hit_at_2": id_hits[1],
                "jd_hit_at_3": id_hits[2],
                "title_hit_at_1": title_hits[0],
                "title_hit_at_2": title_hits[1],
                "title_hit_at_3": title_hits[2],
                "llm_used": bool(parsed.get("llm_used")),
                "parser_mode": parsed.get("parser_mode", ""),
                "llm_warning": parsed.get("llm_warning", ""),
                "extracted_skills": parsed.get("skills", []),
                "skill_count": len(parsed.get("skills") or []),
                "parse_ms": round(parse_ms, 2),
                "total_ms": round((time.perf_counter() - case_started) * 1000, 2),
            }
        )
        print(f"[{index}/{len(manifest)}] {item['sample_id']} llm={parsed.get('llm_used', False)} skills={len(parsed.get('skills') or [])}", flush=True)

    total_ms = (time.perf_counter() - started) * 1000
    count = len(rows)
    report = {
        "status": "completed",
        "mode": "real_pdf_llm_resume_parser_formal_two_stage",
        "samples": count,
        "training_profiles": training_profiles,
        "llm_used_cases": sum(row["llm_used"] for row in rows),
        "llm_fallback_cases": sum(not row["llm_used"] for row in rows),
        "role_top1_accuracy": sum(row["role_hit"] for row in rows) / max(1, count),
        "strict_jd_id_top1_recall": sum(row["jd_hit_at_1"] for row in rows) / max(1, count),
        "strict_jd_id_top2_recall": sum(row["jd_hit_at_2"] for row in rows) / max(1, count),
        "strict_jd_id_top3_recall": sum(row["jd_hit_at_3"] for row in rows) / max(1, count),
        "normalized_title_top1_recall": sum(row["title_hit_at_1"] for row in rows) / max(1, count),
        "normalized_title_top2_recall": sum(row["title_hit_at_2"] for row in rows) / max(1, count),
        "normalized_title_top3_recall": sum(row["title_hit_at_3"] for row in rows) / max(1, count),
        "total_ms": round(total_ms, 2),
        "average_total_ms": round(total_ms / max(1, count), 2),
        "average_parse_ms": round(sum(row["parse_ms"] for row in rows) / max(1, count), 2),
        "average_skill_count": round(sum(row["skill_count"] for row in rows) / max(1, count), 2),
        "llm_evaluation_valid": sum(row["llm_used"] for row in rows) == count,
        "llm_evaluation_warning": (
            "Not a valid LLM accuracy evaluation because one or more cases fell back to the local parser."
            if any(not row["llm_used"] for row in rows)
            else ""
        ),
        "metric_note": "Strict JD metrics compare record IDs; normalized title metrics compare accepted canonical job-title labels.",
    }
    (args.output / "case_metrics.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8"
    )
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
