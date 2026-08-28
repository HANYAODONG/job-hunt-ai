from datetime import date

from scripts.audit_jd_quality import audit, clean_noise, inflation_score, parse_date


def test_parse_date_supports_standard_dataset_formats():
    assert parse_date("2026/7/13").isoformat() == "2026-07-13"
    assert parse_date("2025-01-02").isoformat() == "2025-01-02"


def test_noise_cleaning_removes_culture_but_keeps_duties():
    cleaned, score, reasons, removed = clean_noise(
        "负责Python后端服务开发\n符合公司价值观：客户为先、拼搏担当"
    )
    assert "Python" in cleaned
    assert "价值观" not in cleaned
    assert score > 0
    assert "company_culture" in reasons
    assert removed


def test_noise_cleaning_flags_placeholder_as_high_noise():
    cleaned, score, reasons, _ = clean_noise(
        "请您详见岗位意向中的岗位职责，岗位要求未提供展开要求"
    )
    assert cleaned
    assert score >= 0.35
    assert "placeholder" in reasons


def test_government_contact_is_kept_as_required_evidence():
    cleaned, score, reasons, removed = clean_noise(
        "职位简介：负责信息系统维护\n备注：咨询电话010-12345678",
        source_type="government",
    )
    assert "咨询电话" in cleaned
    assert "contact_or_application" not in reasons
    assert not removed
    assert score < 0.35


def test_inflation_marks_skill_stuffing():
    score, reasons = inflation_score(
        {
            "skill_count": 25,
            "strong_requirement_count": 8,
            "degree_requirement_count": 2,
            "max_years_experience": 12,
        },
        family_skill_median=7,
    )
    assert score >= 0.65
    assert "skill_stuffing" in reasons


def test_audit_produces_required_fields_and_duplicate_trace():
    rows = [
        {
            "job_id": "J1",
            "title": "后端工程师",
            "description": "负责Python后端服务开发和接口设计，熟悉数据库、缓存、消息队列以及微服务架构设计。",
            "skills": ["Python", "MySQL"],
            "job_family": "后端开发工程师",
            "source_type": "enterprise",
            "source": "company_a",
            "publish_time": "2026-01-01",
        },
        {
            "job_id": "J2",
            "title": "后端开发",
            "description": "负责Python后端服务开发和接口设计，熟悉数据库、缓存、消息队列以及微服务架构设计。",
            "skills": ["Python", "MySQL"],
            "job_family": "后端开发工程师",
            "source_type": "government",
            "source": "government_2025",
            "publish_time": "2025-01-01",
        },
    ]
    audited, report, _ = audit(rows, as_of=date(2026, 1, 2))
    assert audited[1]["is_duplicate"] is True
    assert audited[1]["duplicate_of"] == "J1"
    assert audited[0]["verified_by_multi_source"] is True
    for field in ("is_duplicate", "noise_score", "inflation_score", "source_count", "verified_by_multi_source"):
        assert field in audited[0]
    assert report["acceptance"]["required_fields_complete"] is True
    assert report["acceptance"]["source_evidence_complete"] is True
    assert audited[0]["source_evidence"]["current"]["source_name"] == "company_a"
    assert audited[1]["source_evidence"]["record_level_matches"]
    assert audited[0]["verification_scope"] in {"record_duplicate_group", "standard_job_family"}


def test_inflation_adds_role_mismatch_evidence():
    score, reasons = inflation_score(
        {
            "skill_count": 31,
            "strong_requirement_count": 2,
            "degree_requirement_count": 1,
            "max_years_experience": 10,
            "is_senior_role": False,
            "is_vague_title": True,
        },
        family_skill_median=12,
    )
    assert score >= 0.65
    assert "experience_role_mismatch" in reasons
    assert "broad_skill_scope_for_role" in reasons
