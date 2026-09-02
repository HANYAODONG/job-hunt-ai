from __future__ import annotations

import json

import pytest

from scripts.generate_v2_kg_features import normalize, sha256_lf, skill_set
from scripts.import_role_pool_v2_graph import batches
from scripts.validate_role_pool_v2_runtime import validate


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_kg_helpers_normalize_skills_and_line_endings(tmp_path):
    crlf_source = tmp_path / "rows-crlf.jsonl"
    lf_source = tmp_path / "rows-lf.jsonl"
    crlf_source.write_bytes(b'{"id":1}\r\n')
    lf_source.write_bytes(b'{"id":1}\n')

    assert normalize(" Python ") == "python"
    assert skill_set({"skills": ["Python", " python ", "SQL"]}) == {"python", "sql"}
    assert sha256_lf(crlf_source) == sha256_lf(lf_source)


def test_graph_batches_preserve_all_rows():
    assert list(batches(({"id": value} for value in range(5)), 2)) == [
        [{"id": 0}, {"id": 1}],
        [{"id": 2}, {"id": 3}],
        [{"id": 4}],
    ]


def test_runtime_validator_accepts_identical_candidate_pairs(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    bm25 = tmp_path / "bm25.jsonl"
    semantic = tmp_path / "semantic.jsonl"
    kg = tmp_path / "kg.jsonl"
    fusion = tmp_path / "fusion.jsonl"
    write_jsonl(jobs, [{"job_id": "JOB1"}, {"job_id": "JOB2"}])
    write_jsonl(bm25, [{"query_id": "Q1", "candidates": [{"job_id": "JOB1"}, {"job_id": "JOB2"}]}])
    write_jsonl(semantic, [{"query_id": "Q1", "candidates": [{"job_id": "JOB2"}, {"job_id": "JOB1"}]}])
    write_jsonl(kg, [{"query_id": "Q1", "job_id": "JOB1"}, {"query_id": "Q1", "job_id": "JOB2"}])
    write_jsonl(fusion, [{"query_id": "Q1", "results": [{"job_id": "JOB1"}, {"job_id": "JOB2"}]}])

    result = validate(jobs, bm25, semantic, kg, fusion)

    assert result["status"] == "passed"
    assert result["jobs"] == 2
    assert result["queries"] == 1
    assert result["candidate_pairs"] == 2


def test_runtime_validator_rejects_mixed_candidate_sets(tmp_path):
    jobs = tmp_path / "jobs.jsonl"
    bm25 = tmp_path / "bm25.jsonl"
    semantic = tmp_path / "semantic.jsonl"
    kg = tmp_path / "kg.jsonl"
    fusion = tmp_path / "fusion.jsonl"
    write_jsonl(jobs, [{"job_id": "JOB1"}, {"job_id": "JOB2"}])
    write_jsonl(bm25, [{"query_id": "Q1", "candidates": [{"job_id": "JOB1"}]}])
    write_jsonl(semantic, [{"query_id": "Q1", "candidates": [{"job_id": "JOB2"}]}])
    write_jsonl(kg, [{"query_id": "Q1", "job_id": "JOB1"}])
    write_jsonl(fusion, [{"query_id": "Q1", "results": [{"job_id": "JOB1"}]}])

    with pytest.raises(ValueError, match="Candidate pairs differ"):
        validate(jobs, bm25, semantic, kg, fusion)
