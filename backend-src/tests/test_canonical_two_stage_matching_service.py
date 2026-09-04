from app.services.canonical_two_stage_matching_service import CanonicalTwoStageMatchingService, _skill_set


def test_overlapping_language_labels_count_as_one_requirement_group():
    service = CanonicalTwoStageMatchingService()
    job = {
        "required_skills": ["C", "C++", "Python", "机器学习", "大模型预训练", "大模型微调", "强化学习", "Agent"],
    }
    metrics = service._score_job(
        _skill_set(["C/C++", "Python", "Machine Learning", "SFT", "RLHF", "强化学习", "Agent"]),
        job,
    )

    # C/C++ is one capability, and SFT/RLHF are evidence for model
    # fine-tuning. The missing pre-training requirement remains visible.
    assert metrics["recall"] > 0.8
    assert "大模型预训练" in metrics["missing_labels"]
    assert "C++" in metrics["matched_labels"]
    assert "大模型微调" in metrics["matched_labels"]


def test_extra_resume_skills_do_not_crush_a_relevant_jd_score():
    service = CanonicalTwoStageMatchingService()
    job = {"required_skills": ["Python", "SQL", "数据工程"]}
    metrics = service._score_job(
        _skill_set(["Python", "SQL", "数据工程", "TensorFlow", "PyTorch", "Linux", "Git", "Docker"]),
        job,
    )

    assert metrics["score"] > 0.75
    assert metrics["missing_labels"] == set()


def test_sparse_jd_keeps_fit_score_but_is_marked_low_information():
    service = CanonicalTwoStageMatchingService()
    metrics = service._score_job(
        _skill_set(["C", "C++", "Python", "Go"]),
        {"required_skills": ["C", "C++", "Python", "Go"]},
    )

    assert metrics["recall"] == 1.0
    assert metrics["score"] == 1.0
    assert metrics["jd_quality"] == "low_information"
    assert metrics["required_group_count"] == 3  # C/C++ is one capability group


def test_top_role_candidates_are_sorted_by_the_displayed_role_score():
    service = CanonicalTwoStageMatchingService()
    service._jobs = [
        {"job_id": "a", "canonical_role_id": "role_a", "canonical_role": "岗位 A", "required_skills": ["Python"], "role_mapping_status": "mapped"},
        {"job_id": "b", "canonical_role_id": "role_b", "canonical_role": "岗位 B", "required_skills": ["SQL"], "role_mapping_status": "mapped"},
    ]
    service._role_weights = {}
    service._role_titles = {"role_a": "岗位 A", "role_b": "岗位 B"}
    service._role_directions = {"role_a": "方向 A", "role_b": "方向 B"}
    result = service.match(
        type("Candidate", (), {"skills": [type("Skill", (), {"name": "Python"})()]})(),
        type("Query", (), {"page": 1, "page_size": 10})(),
        limit=10,
    )
    scores = [row["role_score"] for row in result.explanations["top_role_candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_match_exposes_role_confidence_and_in_role_jd_candidates_separately():
    service = CanonicalTwoStageMatchingService()
    service._jobs = [
        {"job_id": "jd-a", "canonical_role_id": "role_a", "canonical_role": "岗位 A", "canonical_direction": "方向 A", "required_skills": ["Python"], "role_mapping_status": "mapped"},
        {"job_id": "jd-b", "canonical_role_id": "role_a", "canonical_role": "岗位 A", "canonical_direction": "方向 A", "required_skills": ["Python", "SQL"], "role_mapping_status": "mapped"},
    ]
    service._role_weights = {}
    service._role_titles = {"role_a": "岗位 A"}
    service._role_directions = {"role_a": "方向 A"}
    result = service.match(
        type("Candidate", (), {"skills": [type("Skill", (), {"name": "Python"})()]})(),
        type("Query", (), {"page": 1, "page_size": 10})(),
        limit=10,
    )

    assert result.explanations["selected_role_confidence"] is not None
    jd_candidates = result.explanations["selected_role_jd_candidates"]
    assert [row["job_id"] for row in jd_candidates] == ["jd-a", "jd-b"]
    assert jd_candidates[0]["jd_fit_score"] == 1.0
    assert result.jobs[0].search_metadata["jd_fit_score"] == 1.0
    assert result.jobs[0].search_metadata["jd_quality"] == "low_information"


def test_equal_fit_prefers_the_more_informative_jd():
    service = CanonicalTwoStageMatchingService()
    service._jobs = [
        {"job_id": "jd-sparse", "canonical_role_id": "role_a", "canonical_role": "岗位 A", "required_skills": ["Python"], "role_mapping_status": "mapped"},
        {"job_id": "jd-detailed", "canonical_role_id": "role_a", "canonical_role": "岗位 A", "required_skills": ["Python", "SQL", "Linux", "Docker", "Git"], "role_mapping_status": "mapped"},
    ]
    service._role_weights = {}
    service._role_titles = {"role_a": "岗位 A"}
    service._role_directions = {"role_a": "方向 A"}
    result = service.match(
        type("Candidate", (), {"skills": [type("Skill", (), {"name": skill})() for skill in ["Python", "SQL", "Linux", "Docker", "Git"]]})(),
        type("Query", (), {"page": 1, "page_size": 10})(),
        limit=10,
    )

    assert result.explanations["selected_role_jd_candidates"][0]["job_id"] == "jd-detailed"
