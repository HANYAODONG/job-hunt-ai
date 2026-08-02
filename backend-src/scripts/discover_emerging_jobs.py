"""Discover evidence-backed emerging job candidates from normalized JD data.

This is an offline baseline. It proposes candidates for human review and never
updates the canonical job taxonomy automatically.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import FeatureUnion


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "dataset" / "incoming" / "job_bigcompany_final.csv"
DEFAULT_DICTIONARY = (
    REPO_ROOT / "dataset" / "incoming" / "standard_job_title_dictionary.csv"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / "artifacts" / "new_job_discovery" / "new_job_candidates.json"
)

SPLIT_PATTERN = re.compile(r"[;；,，、|/\n]+")
SENTENCE_PATTERN = re.compile(r"(?:\r?\n|[。；;])")
TITLE_NOISE_PATTERN = re.compile(
    r"(?:高级|资深|初级|中级|实习生?|校招|社招|急聘|招聘|岗)$"
)
ROLE_TITLE_PATTERN = re.compile(
    r"(?:工程师|开发|算法|架构师|产品经理|研究员|科学家|运维|测试|"
    r"顾问|专家|设计师|分析师|技术支持|技术负责人|安全)"
)


@dataclass(frozen=True)
class DiscoveryConfig:
    clusters: int
    min_cluster_size: int = 8
    recent_days: int = 180
    min_score: float = 0.45
    top_k: int = 20
    max_features: int = 30_000
    random_state: int = 42
    evidence_limit: int = 5
    min_technical_terms: int = 2
    min_role_title_share: float = 0.50
    max_cluster_share: float = 0.05


def first_text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def split_terms(value: Any) -> list[str]:
    if isinstance(value, list):
        values = value
    elif value is None:
        values = []
    else:
        values = SPLIT_PATTERN.split(str(value))

    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = str(raw).strip()
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            output.append(item)
    return output


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text or text.startswith("0001-01-01"):
        return None

    try:
        number = float(text)
        if number > 10_000_000_000:
            return datetime.fromtimestamp(number / 1000).date()
    except (ValueError, OverflowError, OSError):
        pass

    date_part = text.split("T", 1)[0].split(" ", 1)[0]
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(date_part, fmt).date()
        except ValueError:
            continue
    return None


def normalize_title(value: str) -> str:
    title = re.sub(r"\s+", " ", value).strip(" -_/|")
    title = re.sub(r"[-_|｜].*$", "", title).strip()
    previous = None
    while title and title != previous:
        previous = title
        title = TITLE_NOISE_PATTERN.sub("", title).strip()
    return title or value.strip()


def normalize_job(record: dict[str, Any], row_number: int) -> dict[str, Any]:
    job_id = first_text(record, "job_id", "id") or f"row_{row_number:06d}"
    title = first_text(record, "title", "job_title")
    responsibilities = first_text(
        record, "responsibilities", "job_responsibility"
    )
    requirements = first_text(record, "requirements", "job_requirement")
    description = first_text(record, "description", "job_description")
    if not description:
        description = "\n".join(
            part for part in (responsibilities, requirements) if part
        )

    return {
        "job_id": job_id,
        "title": title,
        "normalized_title": normalize_title(title),
        "standard_job": first_text(record, "standard_job", "job_family"),
        "responsibilities": responsibilities,
        "requirements": requirements,
        "description": description,
        "skills": split_terms(record.get("skills") or record.get("required_skills")),
        "traditional_skills": split_terms(record.get("traditional_skills")),
        "new_skills": split_terms(record.get("new_skills")),
        "domain_context": split_terms(record.get("domain_context")),
        "publish_date": parse_date(
            record.get("publish_time") or record.get("publish_time_raw")
        ),
        "publish_time_raw": first_text(
            record, "publish_time_raw", "publish_time"
        ),
        "source": first_text(record, "source", "source_type") or "unknown",
        "company": first_text(record, "company", "company_name"),
    }


def read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            raw_records = [
                json.loads(line) for line in handle if line.strip()
            ]
    elif path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_records = payload if isinstance(payload, list) else payload.get("jobs", [])
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            raw_records = list(csv.DictReader(handle))

    jobs = [
        normalize_job(record, index)
        for index, record in enumerate(raw_records, start=1)
    ]
    return [job for job in jobs if job["title"] and job["description"]]


def deduplicate_jobs(jobs: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Remove exact reposts while retaining the newest dated evidence row."""

    selected: dict[str, dict[str, Any]] = {}
    for job in jobs:
        key_text = "|".join(
            [
                job["title"],
                job["responsibilities"],
                job["requirements"],
            ]
        )
        key = re.sub(r"\s+", "", key_text).casefold()
        previous = selected.get(key)
        if previous is None:
            selected[key] = job
            continue
        previous_date = previous["publish_date"] or date.min
        current_date = job["publish_date"] or date.min
        if current_date > previous_date:
            selected[key] = job
    unique_jobs = list(selected.values())
    return unique_jobs, len(jobs) - len(unique_jobs)


def read_taxonomy(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "name": first_text(row, "standard_job_title", "standard_job", "title"),
            "category": first_text(row, "standard_category", "category"),
            "keywords": first_text(row, "match_keywords", "keywords"),
        }
        for row in rows
        if first_text(row, "standard_job_title", "standard_job", "title")
    ]


def build_document(job: dict[str, Any]) -> str:
    title = " ".join([job["title"]] * 4)
    new_skills = " ".join(job["new_skills"] * 4)
    skills = " ".join(job["skills"] * 2)
    domains = " ".join(job["domain_context"] * 2)
    return " ".join(
        [
            title,
            new_skills,
            skills,
            domains,
            job["responsibilities"],
            job["requirements"],
        ]
    )


def build_vectorizer(max_features: int) -> FeatureUnion:
    char_features = max(2_000, int(max_features * 0.65))
    word_features = max(1_000, max_features - char_features)
    return FeatureUnion(
        [
            (
                "char",
                TfidfVectorizer(
                    analyzer="char",
                    ngram_range=(2, 4),
                    min_df=2,
                    max_df=0.98,
                    max_features=char_features,
                    sublinear_tf=True,
                ),
            ),
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    token_pattern=r"(?u)\b[\w.+#-]{2,}\b",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_df=0.98,
                    max_features=word_features,
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def taxonomy_text(entry: dict[str, str]) -> str:
    keywords = re.sub(r"[.*+?^${}()|[\]\\]", " ", entry["keywords"])
    return f"{entry['name']} {entry['name']} {entry['category']} {keywords}"


def scaled_support(size: int, min_cluster_size: int) -> float:
    target = max(40, min_cluster_size * 5)
    return min(1.0, math.log1p(size) / math.log1p(target))


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, value))))


def trend_metrics(
    cluster_jobs: Sequence[dict[str, Any]],
    latest_date: date | None,
    recent_days: int,
    global_recent_share: float,
) -> dict[str, Any]:
    if latest_date is None:
        return {
            "score": 0.5,
            "recent_count": 0,
            "historical_count": 0,
            "recent_share": None,
            "lift_vs_dataset": None,
        }

    cutoff = latest_date - timedelta(days=recent_days)
    dated = [job for job in cluster_jobs if job["publish_date"] is not None]
    recent = sum(job["publish_date"] >= cutoff for job in dated)
    historical = len(dated) - recent
    if not dated:
        return {
            "score": 0.5,
            "recent_count": 0,
            "historical_count": 0,
            "recent_share": None,
            "lift_vs_dataset": None,
        }

    recent_share = recent / len(dated)
    baseline = max(global_recent_share, 1e-6)
    lift = recent_share / baseline
    score = sigmoid(math.log(max(lift, 1e-6)) * 1.5)
    return {
        "score": round(score, 4),
        "recent_count": recent,
        "historical_count": historical,
        "recent_share": round(recent_share, 4),
        "lift_vs_dataset": round(lift, 4),
    }


def frequent_terms(
    jobs: Sequence[dict[str, Any]],
    field: str,
    minimum_share: float,
    maximum_share: float = 1.0,
    limit: int = 12,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for job in jobs:
        seen: set[str] = set()
        for value in job[field]:
            key = value.casefold()
            if key and key not in seen:
                counts[key] += 1
                display.setdefault(key, value)
                seen.add(key)

    output = []
    for key, count in counts.most_common():
        share = count / len(jobs)
        if minimum_share <= share <= maximum_share:
            output.append(
                {
                    "name": display[key],
                    "support": count,
                    "share": round(share, 4),
                }
            )
        if len(output) >= limit:
            break
    return output


def representative_sentences(
    jobs: Sequence[dict[str, Any]],
    keywords: Sequence[str],
    limit: int = 5,
) -> list[str]:
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    keyword_keys = [item.casefold() for item in keywords]
    for job in jobs:
        for sentence in SENTENCE_PATTERN.split(job["responsibilities"]):
            cleaned = re.sub(r"^\s*\d+[、.)．]?\s*", "", sentence).strip()
            key = cleaned.casefold()
            if len(cleaned) < 12 or key in seen:
                continue
            seen.add(key)
            hits = sum(keyword in key for keyword in keyword_keys)
            candidates.append((hits, min(len(cleaned), 180), cleaned[:180]))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in candidates[:limit]]


def choose_candidate_name(
    jobs: Sequence[dict[str, Any]],
    member_matrix: Any,
    centroid: np.ndarray,
) -> str:
    similarities = cosine_similarity(member_matrix, centroid.reshape(1, -1)).ravel()
    central_order = np.argsort(-similarities)
    title_counts = Counter(job["normalized_title"] for job in jobs)
    role_order = [
        index
        for index in central_order
        if ROLE_TITLE_PATTERN.search(jobs[int(index)]["normalized_title"])
    ]
    candidate_order = role_order or list(central_order)
    best_index = max(
        candidate_order[: min(30, len(candidate_order))],
        key=lambda index: (
            title_counts[jobs[int(index)]["normalized_title"]],
            similarities[int(index)],
        ),
    )
    return jobs[int(best_index)]["normalized_title"]


def discover(
    jobs: list[dict[str, Any]],
    taxonomy: list[dict[str, str]],
    config: DiscoveryConfig,
) -> dict[str, Any]:
    if len(jobs) < max(4, config.min_cluster_size):
        raise ValueError("Not enough valid jobs for clustering")

    cluster_count = min(max(2, config.clusters), len(jobs) - 1)
    documents = [build_document(job) for job in jobs]
    vectorizer = build_vectorizer(config.max_features)
    matrix = vectorizer.fit_transform(documents)

    taxonomy_documents = [entry["name"] for entry in taxonomy]
    title_vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 4),
        min_df=1,
        max_features=max(3_000, config.max_features // 3),
        sublinear_tf=True,
    )
    title_corpus = [job["normalized_title"] for job in jobs] + taxonomy_documents
    title_vectorizer.fit(title_corpus)
    title_matrix = title_vectorizer.transform(
        [job["normalized_title"] for job in jobs]
    )

    model = MiniBatchKMeans(
        n_clusters=cluster_count,
        random_state=config.random_state,
        batch_size=min(2048, max(256, len(jobs))),
        n_init=10,
        max_iter=200,
        reassignment_ratio=0.01,
    )
    labels = model.fit_predict(matrix)

    if taxonomy:
        taxonomy_matrix = title_vectorizer.transform(taxonomy_documents)
        taxonomy_names = [entry["name"] for entry in taxonomy]
    else:
        taxonomy_matrix = None
        taxonomy_names = []

    parsed_dates = [job["publish_date"] for job in jobs if job["publish_date"]]
    latest_date = max(parsed_dates) if parsed_dates else None
    if latest_date:
        cutoff = latest_date - timedelta(days=config.recent_days)
        global_recent_share = (
            sum(value >= cutoff for value in parsed_dates) / len(parsed_dates)
        )
    else:
        global_recent_share = 0.0

    candidates: list[dict[str, Any]] = []
    cluster_sizes = Counter(int(label) for label in labels)
    for cluster_id, size in sorted(cluster_sizes.items()):
        if size < config.min_cluster_size:
            continue
        if size / len(jobs) > config.max_cluster_share:
            continue

        indices = np.flatnonzero(labels == cluster_id)
        cluster_jobs = [jobs[int(index)] for index in indices]
        role_title_share = (
            sum(bool(ROLE_TITLE_PATTERN.search(job["normalized_title"])) for job in cluster_jobs)
            / size
        )
        if role_title_share < config.min_role_title_share:
            continue
        member_matrix = matrix[indices]
        member_title_matrix = title_matrix[indices]
        centroid = np.asarray(model.cluster_centers_[cluster_id], dtype=np.float64)
        coherence = float(
            cosine_similarity(member_matrix, centroid.reshape(1, -1)).mean()
        )

        if taxonomy_matrix is not None:
            title_centroid = np.asarray(member_title_matrix.mean(axis=0)).ravel()
            taxonomy_scores = cosine_similarity(
                title_centroid.reshape(1, -1), taxonomy_matrix
            ).ravel()
            nearest_order = np.argsort(-taxonomy_scores)[:3]
            nearest_taxonomy = [
                {
                    "name": taxonomy_names[int(index)],
                    "similarity": round(float(taxonomy_scores[int(index)]), 4),
                }
                for index in nearest_order
            ]
            max_taxonomy_similarity = float(taxonomy_scores[nearest_order[0]])
        else:
            nearest_taxonomy = []
            max_taxonomy_similarity = 0.0

        novelty_score = 1.0 - max(0.0, min(1.0, max_taxonomy_similarity))
        trend = trend_metrics(
            cluster_jobs,
            latest_date,
            config.recent_days,
            global_recent_share,
        )
        new_skill_jobs = sum(bool(job["new_skills"]) for job in cluster_jobs)
        new_skill_score = new_skill_jobs / size
        support_score = scaled_support(size, config.min_cluster_size)

        standard_counts = Counter(
            job["standard_job"] for job in cluster_jobs if job["standard_job"]
        )
        dominant_standard, dominant_count = (
            standard_counts.most_common(1)[0] if standard_counts else ("", 0)
        )
        taxonomy_disagreement = 1.0 - (dominant_count / size)

        score = (
            novelty_score * 0.30
            + float(trend["score"]) * 0.25
            + new_skill_score * 0.20
            + coherence * 0.10
            + support_score * 0.10
            + taxonomy_disagreement * 0.05
        )
        if score < config.min_score:
            continue

        required_skills = frequent_terms(
            cluster_jobs, "skills", minimum_share=0.35, limit=12
        )
        bonus_skills = frequent_terms(
            cluster_jobs,
            "skills",
            minimum_share=0.12,
            maximum_share=0.349999,
            limit=12,
        )
        emerging_skills = frequent_terms(
            cluster_jobs, "new_skills", minimum_share=0.10, limit=12
        )
        industries = frequent_terms(
            cluster_jobs, "domain_context", minimum_share=0.08, limit=8
        )
        if len(required_skills) + len(emerging_skills) < config.min_technical_terms:
            continue
        observed_name = choose_candidate_name(cluster_jobs, member_matrix, centroid)
        taxonomy_name_set = {item["name"].casefold() for item in taxonomy}
        name = observed_name
        if emerging_skills and (
            len(observed_name) <= 6
            or observed_name.casefold() in taxonomy_name_set
        ):
            directions = "/".join(
                item["name"] for item in emerging_skills[:2]
            )
            name = f"{observed_name}（{directions}方向）"
        responsibility_keywords = [
            item["name"] for item in required_skills[:5] + emerging_skills[:5]
        ]
        core_responsibilities = representative_sentences(
            cluster_jobs, responsibility_keywords
        )

        member_similarities = cosine_similarity(
            member_matrix, centroid.reshape(1, -1)
        ).ravel()
        evidence_order = np.argsort(-member_similarities)[: config.evidence_limit]
        evidence = []
        for local_index in evidence_order:
            job = cluster_jobs[int(local_index)]
            evidence.append(
                {
                    "job_id": job["job_id"],
                    "title": job["title"],
                    "standard_job": job["standard_job"],
                    "publish_time": job["publish_time_raw"],
                    "source": job["source"],
                    "company": job["company"],
                    "skills": job["skills"][:15],
                    "responsibility_excerpt": job["responsibilities"][:240],
                    "cluster_similarity": round(
                        float(member_similarities[int(local_index)]), 4
                    ),
                }
            )

        dominant_share = dominant_count / size
        candidate_type = (
            "taxonomy_gap"
            if novelty_score >= 0.55 and dominant_share < 0.60
            else "emerging_specialization"
        )
        candidates.append(
            {
                "candidate_id": f"emerging_cluster_{cluster_id:03d}",
                "candidate_name": name,
                "representative_observed_title": observed_name,
                "candidate_type": candidate_type,
                "review_status": "candidate_requires_human_review",
                "discovery_score": round(score, 4),
                "score_breakdown": {
                    "taxonomy_novelty": round(novelty_score, 4),
                    "recent_growth": trend["score"],
                    "new_skill_signal": round(new_skill_score, 4),
                    "cluster_coherence": round(coherence, 4),
                    "support": round(support_score, 4),
                    "taxonomy_disagreement": round(taxonomy_disagreement, 4),
                    "role_title_share": round(role_title_share, 4),
                },
                "supporting_jd_count": size,
                "dominant_existing_job": {
                    "name": dominant_standard,
                    "share": round(dominant_share, 4),
                },
                "nearest_existing_jobs": nearest_taxonomy,
                "trend": {
                    **trend,
                    "window_days": config.recent_days,
                    "dataset_latest_date": (
                        latest_date.isoformat() if latest_date else None
                    ),
                },
                "definition": {
                    "core_responsibilities": core_responsibilities,
                    "required_skills": required_skills,
                    "bonus_skills": bonus_skills,
                    "emerging_skills": emerging_skills,
                    "industry_scenarios": industries,
                },
                "standard_job_distribution": [
                    {"name": item, "count": count, "share": round(count / size, 4)}
                    for item, count in standard_counts.most_common(8)
                ],
                "evidence": evidence,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["discovery_score"],
            item["supporting_jd_count"],
        ),
        reverse=True,
    )
    candidates = candidates[: config.top_k]

    return {
        "metadata": {
            "algorithm": "tfidf_minibatch_kmeans_evidence_baseline",
            "job_count": len(jobs),
            "cluster_count": cluster_count,
            "taxonomy_size": len(taxonomy),
            "latest_publish_date": latest_date.isoformat() if latest_date else None,
            "recent_days": config.recent_days,
            "global_recent_share": round(global_recent_share, 4),
            "minimum_cluster_size": config.min_cluster_size,
            "minimum_discovery_score": config.min_score,
            "minimum_technical_terms": config.min_technical_terms,
            "minimum_role_title_share": config.min_role_title_share,
            "maximum_cluster_share": config.max_cluster_share,
            "score_weights": {
                "taxonomy_novelty": 0.30,
                "recent_growth": 0.25,
                "new_skill_signal": 0.20,
                "cluster_coherence": 0.10,
                "support": 0.10,
                "taxonomy_disagreement": 0.05,
            },
            "warning": (
                "Candidates are statistical signals, not approved job definitions. "
                "Human review and source verification are required."
            ),
        },
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def default_cluster_count(job_count: int) -> int:
    return max(8, min(160, round(math.sqrt(job_count) * 1.25)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover evidence-backed emerging job candidates from JD data"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dictionary", type=Path, default=DEFAULT_DICTIONARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clusters", type=int, default=0, help="0 selects automatically")
    parser.add_argument("--min-cluster-size", type=int, default=8)
    parser.add_argument("--recent-days", type=int, default=180)
    parser.add_argument("--min-score", type=float, default=0.45)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--max-features", type=int, default=30_000)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--evidence-limit", type=int, default=5)
    parser.add_argument("--min-technical-terms", type=int, default=2)
    parser.add_argument("--min-role-title-share", type=float, default=0.50)
    parser.add_argument("--max-cluster-share", type=float, default=0.05)
    parser.add_argument("--limit", type=int, default=0, help="Debug sample size")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input.resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    input_jobs = read_records(input_path)
    jobs, duplicate_count = deduplicate_jobs(input_jobs)
    if args.limit > 0:
        jobs = jobs[: args.limit]
    taxonomy = read_taxonomy(args.dictionary.resolve())
    clusters = args.clusters or default_cluster_count(len(jobs))
    config = DiscoveryConfig(
        clusters=clusters,
        min_cluster_size=args.min_cluster_size,
        recent_days=args.recent_days,
        min_score=args.min_score,
        top_k=args.top_k,
        max_features=args.max_features,
        random_state=args.random_state,
        evidence_limit=args.evidence_limit,
        min_technical_terms=args.min_technical_terms,
        min_role_title_share=args.min_role_title_share,
        max_cluster_share=args.max_cluster_share,
    )
    result = discover(jobs, taxonomy, config)
    result["metadata"]["input_job_count"] = len(input_jobs)
    result["metadata"]["exact_duplicate_jd_count"] = duplicate_count

    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "input": str(input_path),
        "output": str(output_path),
        "job_count": result["metadata"]["job_count"],
        "clusters": result["metadata"]["cluster_count"],
        "candidate_count": result["candidate_count"],
        "top_candidates": [
            {
                "name": item["candidate_name"],
                "score": item["discovery_score"],
                "supporting_jd_count": item["supporting_jd_count"],
                "type": item["candidate_type"],
            }
            for item in result["candidates"][:10]
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
