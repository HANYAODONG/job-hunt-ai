from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"

class ExperienceLevel(str, Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    EXECUTIVE = "executive"

class Location(BaseModel):
    city: str
    state: str
    country: str = "USA"
    coordinates: Optional[Dict[str, float]] = None

class Salary(BaseModel):
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    currency: str = "USD"
    period: str = "yearly"  # yearly, monthly, hourly

class Benefit(BaseModel):
    name: str
    description: Optional[str] = None
    category: str  # health, retirement, visa, etc.

class Job(BaseModel):
    id: str
    title: str
    description: str
    company_name: str
    location: Location
    job_type: JobType
    experience_level: ExperienceLevel
    salary: Optional[Salary] = None
    benefits: List[Benefit] = []
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    responsibilities: List[str] = []
    requirements: List[str] = []
    posted_date: datetime
    application_deadline: Optional[datetime] = None
    remote_allowed: bool = False
    visa_sponsorship: bool = False
    source_url: Optional[str] = None
    apply_url: Optional[str] = None  # Direct application URL
    rerank_score: Optional[float] = None  # Reranking score for personalized results
    search_metadata: Optional[Dict[str, Any]] = None
    feature_vector: Optional[Dict[str, float]] = None
    job_family: Optional[str] = None  # 岗位族
    source: Optional[str] = None  # 数据来源
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class JobSearchQuery(BaseModel):
    query: str
    location: Optional[str] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    job_type: Optional[JobType] = None
    experience_level: Optional[ExperienceLevel] = None
    remote_allowed: Optional[bool] = None
    visa_sponsorship: Optional[bool] = None
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    page: int = 1
    page_size: int = 20

class JobSearchResult(BaseModel):
    jobs: List[Job]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    search_time_ms: float
    reranking_time_ms: Optional[float] = None  # Time spent on reranking
    reranking_statistics: Optional[Dict[str, Any]] = None  # Reranking performance stats
    explanations: Optional[Dict[str, Any]] = None  # Detailed explanations for top jobs
    filtered_out_reasons: Optional[Dict[str, str]] = None  # job_id -> reason filtered
    prompts: Optional[List[str]] = None  # follow-up questions for missing non-trivial constraints