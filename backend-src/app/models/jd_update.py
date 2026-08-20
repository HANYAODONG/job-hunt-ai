from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Domain = Literal["company", "government"]
ProcessingMode = Literal["auto", "manual"]


class JdSubmissionInput(BaseModel):
    domain: Domain = "company"
    job_title: str = Field(min_length=1)
    responsibility: str = ""
    requirement: str = ""
    month: str = ""
    processing_mode: ProcessingMode = "auto"
    job_id: str = ""
    publish_time: str = ""
    recruitment_year: str = ""
    source: str = ""
    source_name: str = ""
    source_url: str = ""
    government_agency: str = ""
    government_department: str = ""
    location: str = ""


class JdSubmitInput(BaseModel):
    domain: Domain = "company"
    preview_id: str = Field(min_length=1)
    processing_mode: ProcessingMode = "auto"


class ExistingJobReviewInput(BaseModel):
    standard_job_title: str = ""
    standard_category: str = ""
    skills: list[dict[str, Any]] = Field(default_factory=list)


class NewJobReviewInput(BaseModel):
    standard_category: str
    standard_job_title: str
    match_keywords: str = ""
    skills: list[dict[str, Any]] = Field(default_factory=list)


class SkillReviewInput(BaseModel):
    decision: Literal["confirmed", "mapped", "invalid", "new_skill"] = "confirmed"
    normalized_skill: str = ""
    kg_display_skill: str = ""
    skill_type: str = ""


class ProfileOverrideInput(BaseModel):
    standard_job: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
