from app.services.role_aware_matching_service import rank_role_aware


def _job(job_id: str, role: str, score: float) -> dict:
    return {
        "job_id": job_id,
        "final_score": score,
        "title": role,
        "standard_job": role,
        "job_family": role,
        "required_skills": ["Java"],
    }


def test_role_gate_selects_one_canonical_role_then_ranks_its_jds():
    result = rank_role_aware(
        [
            _job("backend-2", "后端开发工程师", 0.82),
            _job("frontend-1", "前端开发工程师", 0.95),
            _job("backend-1", "后端开发工程师", 0.78),
        ],
        top_k=3,
        role_top_k=1,
    )

    assert result["selected_role"]["canonical_role"] == "前端开发工程师"
    assert [item["job_id"] for item in result["results"]] == ["frontend-1"]
    assert result["results"][0]["final_score"] == 0.95
    assert result["mapped_candidate_count"] == 3


def test_unmapped_candidates_are_visible_but_do_not_displace_mapped_roles():
    result = rank_role_aware(
        [
            _job("unmapped-1", "不存在的岗位标签", 0.99),
            _job("backend-1", "后端开发工程师", 0.80),
        ]
    )

    assert result["selected_role"]["canonical_role"] == "后端开发工程师"
    assert [item["job_id"] for item in result["results"]] == ["backend-1"]
    assert result["candidate_count"] == 2
    assert result["mapped_candidate_count"] == 1
