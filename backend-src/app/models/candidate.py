from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class EducationLevel(str, Enum):
    HIGH_SCHOOL = "high_school"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORATE = "doctorate"

class Experience(BaseModel):
    company: str
    position: str
    start_date: datetime
    end_date: Optional[datetime] = None
    description: str
    skills_used: List[str] = []
    achievements: List[str] = []

class Education(BaseModel):
    institution: str
    degree: str
    field_of_study: str
    graduation_date: Optional[datetime] = None
    gpa: Optional[float] = None

class Skill(BaseModel):
    name: str
    level: str  # beginner, intermediate, advanced, expert
    years_experience: Optional[int] = None
    category: str  # technical, soft, language, etc.

class Candidate(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    skills: List[Skill] = []
    experience: List[Experience] = []
    education: List[Education] = []
    certifications: List[str] = []
    languages: List[str] = []
    visa_status: Optional[str] = None
    availability: Optional[datetime] = None
    salary_expectation: Optional[int] = None
    preferred_locations: List[str] = []
    resume_file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    target_job_family: Optional[str] = None  # 目标岗位族
    years_experience: Optional[int] = None   # 工作年限
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class CandidateProfile(BaseModel):
    candidate: Candidate
    extracted_skills: List[str] = []
    extracted_experience: List[str] = []
    skill_categories: Dict[str, List[str]] = {}
    experience_summary: str = ""
    match_score: Optional[float] = None
    # Extended attributes for hard constraints and personalization
    visa_status: Optional[str] = None
    degree_level: Optional[EducationLevel] = None
    certifications: List[str] = []
    security_clearance: Optional[str] = None
    languages: List[str] = []

class ResumeUpload(BaseModel):
    file_name: str
    file_size: int
    file_type: str
    upload_date: datetime

class CandidateJobMatch(BaseModel):
    job_id: str
    candidate_id: str
    match_score: float
    matching_skills: List[str] = []
    missing_skills: List[str] = []
    experience_match: float
    location_match: bool
    salary_match: bool
    visa_match: bool
    overall_fit: str  # excellent, good, fair, poor