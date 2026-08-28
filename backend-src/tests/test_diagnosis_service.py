from __future__ import annotations

from app.services.diagnosis_service import analyze_diagnosis, compute_semantic_score


def test_analyze_diagnosis_matched_and_missing():
    result = analyze_diagnosis(
        candidate_id="cand_001",
        job_id="job_001",
        candidate_skills=["Python", "SQL", "FastAPI"],
        job_required_skills=["Python", "SQL", "Docker", "Kubernetes"],
        job_title="数据工程师",
        semantic_score=0.65,
    )

    assert result["candidate_id"] == "cand_001"
    assert result["job_id"] == "job_001"
    assert set(result["candidate_skills"]) == {"Python", "SQL", "FastAPI"}
    assert set(result["target_job_skills"]) == {"Python", "SQL", "Docker", "Kubernetes"}
    assert set(result["matched_skills"]) == {"Python", "SQL"}
    assert set(result["missing_skills"]) == {"Docker", "Kubernetes"}
    assert result["semantic_score"] == 0.65
    # final_score 应在 [0, 1] 内
    assert 0.0 <= result["final_score"] <= 1.0
    assert result["explanation"]
    assert "bm25_score" in result["score_breakdown"]
    assert "semantic_score" in result["score_breakdown"]


def test_analyze_diagnosis_skill_coverage():
    result = analyze_diagnosis(
        candidate_id="c",
        job_id="j",
        candidate_skills=["A", "B"],
        job_required_skills=["A", "B", "C", "D"],
        semantic_score=0.5,
    )
    assert result["skill_coverage"] == 0.5
    assert len(result["matched_skills"]) == 2
    assert len(result["missing_skills"]) == 2


def test_analyze_diagnosis_empty_required_skills():
    result = analyze_diagnosis(
        candidate_id="c",
        job_id="j",
        candidate_skills=["A"],
        job_required_skills=[],
        semantic_score=0.5,
    )
    assert result["skill_coverage"] == 0.0
    assert result["matched_skills"] == []
    assert result["missing_skills"] == []


def test_compute_semantic_score_jaccard_fallback():
    score = compute_semantic_score("python sql fastapi", "python sql docker", nlp_service=None)
    assert 0.0 <= score <= 1.0
    # 词级 Jaccard 应为 2/4 = 0.5
    assert abs(score - 0.5) < 1e-6


def test_compute_semantic_score_empty_text():
    assert compute_semantic_score("", "some text", nlp_service=None) == 0.0
    assert compute_semantic_score("some text", "", nlp_service=None) == 0.0
