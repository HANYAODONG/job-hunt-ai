from __future__ import annotations

from app.services.nlp_service import NLPService
from app.services.resume_service import ResumeService


def test_resume_parser_uses_shared_skill_dictionary_and_years():
    service = NLPService()
    profile = service.extract_candidate_profile(
        "Python Developer with 3 years experience in Django FastAPI SQL PostgreSQL backend development"
    )

    assert {"Python", "Django", "FastAPI", "SQL", "PostgreSQL"}.issubset(profile["skills"])
    assert profile["years_experience"] == 3


def test_resume_parser_extracts_chinese_experience_years():
    service = NLPService()

    assert service._extract_years_experience("具备5年以上Java开发经验") == 5
    assert service._extract_years_experience("拥有3年相关工作经历") == 3


def test_resume_parser_prefers_explicit_skill_stack():
    service = NLPService()
    profile = service.extract_candidate_profile(
        "求职意向：后端开发工程师。\n技能栈：Python、FastAPI、PostgreSQL、Redis。\n"
        "项目中还负责沟通和文档整理。"
    )

    assert profile["skills"] == ["Python", "FastAPI", "PostgreSQL", "Redis"]


def test_skill_category_matching_does_not_use_substrings():
    service = ResumeService()
    categories = service._categorize_skills(["Django", "FastAPI", "Go", "Python"])

    assert {"Django", "FastAPI"}.issubset(categories["frameworks"])
    assert "Django" not in categories["programming_languages"]
    assert {"Go", "Python"}.issubset(categories["programming_languages"])


def test_job_requirements_work_without_spacy_entities():
    service = NLPService()
    service.nlp = None

    requirements = service.extract_job_requirements("要求 Python、FastAPI 和 PostgreSQL 开发经验")

    assert {"Python", "FastAPI", "PostgreSQL"}.issubset(requirements["required_skills"])
    assert requirements["location"] == ""
    assert requirements["salary_range"] == ""
