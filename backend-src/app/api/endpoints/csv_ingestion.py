from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from typing import Dict, Any, Optional
import pandas as pd
import uuid
import re
from datetime import datetime
from pathlib import Path
import logging
import tempfile
import os

from ...models.job import Job, JobType, ExperienceLevel, Location, Salary
from ...services.elasticsearch_service import ElasticsearchService
from ...services.knowledge_graph_service import KnowledgeGraphService

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
es_service = ElasticsearchService()
kg_service = KnowledgeGraphService()

@router.post("/ingest-csv")
async def ingest_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    index_to_elasticsearch: bool = Form(True),
    create_neo4j_nodes: bool = Form(True),
    process_with_nlp: bool = Form(True),
    batch_size: int = Form(100)
) -> Dict[str, Any]:
    """
    Ingest jobs from any CSV file
    
    This endpoint accepts any CSV file and processes it to import jobs into
    Elasticsearch and Neo4j databases.
    
    Parameters:
    - file: CSV file to upload
    - index_to_elasticsearch: Whether to index jobs to Elasticsearch (default: True)
    - create_neo4j_nodes: Whether to create Neo4j nodes (default: True)
    - process_with_nlp: Whether to process jobs with NLP (default: True)
    - batch_size: Number of jobs to process per batch (default: 100)
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV file")
        
        # Save uploaded file temporarily
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        
        # Start background task for processing
        background_tasks.add_task(
            process_csv_file, 
            temp_file.name, 
            file.filename,
            index_to_elasticsearch,
            create_neo4j_nodes,
            process_with_nlp,
            batch_size
        )
        
        return {
            "message": f"CSV ingestion started in background for file: {file.filename}",
            "status": "processing",
            "filename": file.filename,
            "file_size": len(content),
            "options": {
                "index_to_elasticsearch": index_to_elasticsearch,
                "create_neo4j_nodes": create_neo4j_nodes,
                "process_with_nlp": process_with_nlp,
                "batch_size": batch_size
            }
        }
        
    except Exception as e:
        logger.error(f"Error starting CSV ingestion: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting ingestion: {str(e)}")

@router.post("/ingest-swe-csv")
async def ingest_swe_csv(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Ingest jobs from the SWE.csv file
    
    This endpoint processes the SWE.csv file and imports all jobs into
    Elasticsearch and Neo4j databases.
    """
    try:
        # Path to the SWE.csv file
        csv_path = Path(__file__).parent.parent.parent.parent / "SWE.csv"
        
        if not csv_path.exists():
            raise HTTPException(status_code=404, detail="SWE.csv file not found")
        
        # Start background task for processing
        background_tasks.add_task(process_swe_csv, str(csv_path))
        
        return {
            "message": "SWE CSV ingestion started in background",
            "status": "processing",
            "csv_file": str(csv_path)
        }
        
    except Exception as e:
        logger.error(f"Error starting SWE CSV ingestion: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting ingestion: {str(e)}")

@router.get("/ingest-swe-csv/status")
async def get_ingestion_status() -> Dict[str, Any]:
    """
    Get the status of SWE CSV ingestion
    """
    try:
        # Get current job counts
        es_count = 0  # TODO: Add method to get ES job count
        kg_count = 0  # TODO: Add method to get Neo4j job count
        
        return {
            "elasticsearch_jobs": es_count,
            "neo4j_jobs": kg_count,
            "timestamp": datetime.now().isoformat(),
            "status": "CSV ingestion endpoint is working"
        }
        
    except Exception as e:
        logger.error(f"Error getting ingestion status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")

async def process_csv_file(
    csv_path: str, 
    filename: str,
    index_to_elasticsearch: bool = True,
    create_neo4j_nodes: bool = True,
    process_with_nlp: bool = True,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Process any CSV file and import jobs
    """
    start_time = datetime.now()
    
    try:
        logger.info(f"Starting CSV processing from: {filename}")
        
        # Load CSV
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} rows from {filename}")
        
        # Log column information for debugging
        logger.info(f"CSV columns: {list(df.columns)}")
        
        # Process each row
        jobs = []
        for index, row in df.iterrows():
            try:
                job = create_job_from_csv_row(row, filename)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"Error processing row {index} in {filename}: {e}")
                continue
        
        logger.info(f"Created {len(jobs)} job objects from {filename}")
        
        # Process jobs in batches
        results = await process_jobs_in_batches(
            jobs, index_to_elasticsearch, create_neo4j_nodes, batch_size
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            "success": True,
            "message": f"Successfully processed {len(jobs)} jobs from {filename}",
            "filename": filename,
            "total_rows": len(df),
            "valid_jobs": len(jobs),
            "elasticsearch_indexed": results["elasticsearch_count"],
            "neo4j_created": results["neo4j_count"],
            "processing_time_seconds": processing_time,
            "errors": results["errors"]
        }
        
        logger.info(f"CSV processing completed for {filename}: {result}")
        
        # Clean up temporary file
        try:
            os.unlink(csv_path)
        except Exception as e:
            logger.warning(f"Could not delete temp file {csv_path}: {e}")
        
        return result
        
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"Error processing CSV {filename}: {e}")
        
        # Clean up temporary file
        try:
            os.unlink(csv_path)
        except Exception:
            pass
        
        return {
            "success": False,
            "message": f"Error processing CSV {filename}: {str(e)}",
            "filename": filename,
            "total_rows": 0,
            "valid_jobs": 0,
            "elasticsearch_indexed": 0,
            "neo4j_created": 0,
            "processing_time_seconds": processing_time
        }

async def process_swe_csv(csv_path: str) -> Dict[str, Any]:
    """
    Process the SWE.csv file and import jobs
    """
    start_time = datetime.now()
    
    try:
        logger.info(f"Starting SWE CSV processing from: {csv_path}")
        
        # Load CSV
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} rows from SWE.csv")
        
        # Process each row
        jobs = []
        for index, row in df.iterrows():
            try:
                job = create_job_from_swe_row(row)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"Error processing row {index}: {e}")
                continue
        
        logger.info(f"Created {len(jobs)} job objects")
        
        # Index to Elasticsearch
        es_count = 0
        for job in jobs:
            try:
                success = es_service.index_job(job)
                if success:
                    es_count += 1
            except Exception as e:
                logger.warning(f"Error indexing job {job.id}: {e}")
                continue
        
        # Create Neo4j nodes
        kg_count = 0
        for job in jobs:
            try:
                success = kg_service.create_job_node(job)
                if success:
                    kg_count += 1
                    
                    # Create related nodes
                    kg_service.create_company_node(job.company_name, {})
                    kg_service.create_location_node(job.location)
                    
                    # Create skill relationships
                    for skill in job.required_skills:
                        kg_service.create_skill_node(skill)
                        kg_service.create_job_skill_relationship(job.id, skill)
                    
                    # Create company and location relationships
                    kg_service.create_job_company_relationship(job.id, job.company_name)
                    location_id = f"{job.location.city}_{job.location.state}_{job.location.country}"
                    kg_service.create_job_location_relationship(job.id, location_id)
                    
            except Exception as e:
                logger.warning(f"Error creating Neo4j nodes for job {job.id}: {e}")
                continue
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            "success": True,
            "message": f"Successfully processed {len(jobs)} jobs from SWE.csv",
            "total_rows": len(df),
            "valid_jobs": len(jobs),
            "elasticsearch_indexed": es_count,
            "neo4j_created": kg_count,
            "processing_time_seconds": processing_time
        }
        
        logger.info(f"SWE CSV processing completed: {result}")
        return result
        
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"Error processing SWE CSV: {e}")
        return {
            "success": False,
            "message": f"Error processing SWE CSV: {str(e)}",
            "processing_time_seconds": processing_time
        }

def create_job_from_csv_row(row: pd.Series, filename: str = "") -> Job:
    """
    Create a Job object from any CSV row with intelligent field mapping
    """
    try:
        # Generate unique ID
        job_id = str(uuid.uuid4())
        
        # Extract basic information with flexible field mapping
        title = extract_text_field(row, [
            'title', 'job_title', 'position', 'role', 'position_title', 'Position Title',
            'job_name', 'position_name', 'job', 'title'
        ])
        if not title:
            logger.warning(f"No title found in row, skipping")
            return None
        
        # Extract company with flexible mapping
        company_name = extract_text_field(row, [
            'company', 'company_name', 'Company', 'employer', 'organization', 'employer_name',
            'company_name', 'hiring_company', 'recruiter'
        ])
        if not company_name:
            company_name = "Unknown Company"
        
        # Extract location with flexible mapping
        location = extract_location_flexible(row)
        
        # Extract salary information
        salary = extract_salary_flexible(row)
        
        # Extract description/qualifications
        description = extract_text_field(row, [
            'description', 'job_description', 'summary', 'details', 'qualifications', 'Qualifications',
            'requirements', 'job_summary', 'overview', 'responsibilities'
        ])
        if not description:
            description = title  # Use title as fallback
        
        # Extract skills from various fields
        required_skills = extract_skills_flexible(row)
        
        # Determine job type and experience level
        job_type = determine_job_type_flexible(title, description)
        experience_level = determine_experience_level_flexible(title, description)
        
        # Extract work model and remote info
        work_model = extract_text_field(row, [
            'work_model', 'Work Model', 'work_type', 'employment_type', 'work_arrangement',
            'location_type', 'remote', 'work_location'
        ])
        remote_allowed = 'remote' in work_model.lower() if work_model else False
        
        # Extract visa sponsorship
        visa_sponsorship = extract_boolean_field(row, [
            'visa_sponsorship', 'sponsor_visa', 'h1b', 'h1b_sponsored', 'H1b Sponsored',
            'visa_support', 'immigration_support'
        ])
        
        # Extract source URL
        source_url = extract_text_field(row, [
            'url', 'source_url', 'link', 'job_url', 'apply_url', 'application_url', 'Apply'
        ])
        
        # Create Job object
        job = Job(
            id=job_id,
            title=title,
            description=description,
            company_name=company_name,
            location=location,
            job_type=job_type,
            experience_level=experience_level,
            salary=salary,
            benefits=[],
            required_skills=required_skills,
            preferred_skills=[],
            responsibilities=[],
            requirements=[],
            posted_date=datetime.now(),
            application_deadline=None,
            remote_allowed=remote_allowed,
            visa_sponsorship=visa_sponsorship,
            source_url=source_url if source_url != 'nan' else None
        )
        
        return job
        
    except Exception as e:
        logger.error(f"Error creating job from row: {e}")
        return None

def create_job_from_swe_row(row: pd.Series) -> Job:
    """
    Create a Job object from a SWE.csv row
    """
    try:
        # Generate unique ID
        job_id = str(uuid.uuid4())
        
        # Extract basic information
        title = str(row.get('Position Title', '')).strip()
        if not title:
            return None
        
        # Extract company
        company_name = str(row.get('Company', 'Unknown Company')).strip()
        
        # Extract location
        location_str = str(row.get('Location', '')).strip()
        city, state = parse_location(location_str)
        
        # Extract salary
        salary_str = str(row.get('Salary', '')).strip()
        salary = parse_salary(salary_str)
        
        # Extract qualifications as description
        qualifications = str(row.get('Qualifications', '')).strip()
        description = f"Position: {title}\n\nQualifications:\n{qualifications}"
        
        # Extract skills from qualifications
        skills = extract_skills_from_text(qualifications)
        
        # Determine job type and experience level
        job_type = determine_job_type(title, qualifications)
        experience_level = determine_experience_level(title, qualifications)
        
        # Extract work model
        work_model = str(row.get('Work Model', '')).strip()
        remote_allowed = 'remote' in work_model.lower() or 'hybrid' in work_model.lower()
        
        # Extract visa sponsorship
        h1b_sponsored = str(row.get('H1b Sponsored', '')).strip().lower()
        visa_sponsorship = h1b_sponsored in ['yes', 'true', '1']
        
        # Extract new grad status
        is_new_grad = str(row.get('Is New Grad', '')).strip().lower()
        if is_new_grad in ['yes', 'true', '1']:
            experience_level = ExperienceLevel.ENTRY
        
        # Extract source URL
        source_url = str(row.get('Apply', '')).strip()
        
        # Create Job object
        job = Job(
            id=job_id,
            title=title,
            description=description,
            company_name=company_name,
            location=Location(
                city=city,
                state=state,
                country="USA"
            ),
            job_type=job_type,
            experience_level=experience_level,
            salary=salary,
            benefits=[],
            required_skills=skills,
            preferred_skills=[],
            responsibilities=[],
            requirements=qualifications.split('\n') if qualifications else [],
            posted_date=datetime.now(),
            application_deadline=None,
            remote_allowed=remote_allowed,
            visa_sponsorship=visa_sponsorship,
            source_url=source_url if source_url != 'nan' else None
        )
        
        return job
        
    except Exception as e:
        logger.error(f"Error creating job from row: {e}")
        return None

def parse_location(location_str: str) -> tuple:
    """
    Parse location string to extract city and state
    """
    if not location_str or location_str == 'nan':
        return "Unknown", "Unknown"
    
    # Remove quotes and clean up
    location_str = location_str.strip('"').strip()
    
    # Split by comma
    parts = [part.strip() for part in location_str.split(',')]
    
    if len(parts) >= 2:
        city = parts[0]
        state = parts[1]
    else:
        # Try to extract state from single part
        words = location_str.split()
        if len(words) >= 2:
            city = ' '.join(words[:-1])
            state = words[-1]
        else:
            city = location_str
            state = "Unknown"
    
    return city, state

def parse_salary(salary_str: str) -> Salary:
    """
    Parse salary string to extract min and max salary
    """
    if not salary_str or salary_str == 'nan':
        return None
    
    try:
        # Remove currency symbols and clean up
        salary_str = salary_str.replace('$', '').replace(',', '').strip()
        
        # Look for range pattern (e.g., "74000-138000 /yr")
        range_match = re.search(r'(\d+)-(\d+)', salary_str)
        if range_match:
            min_salary = int(range_match.group(1))
            max_salary = int(range_match.group(2))
            return Salary(
                min_salary=min_salary,
                max_salary=max_salary,
                currency="USD",
                period="yearly"
            )
        
        # Look for single number
        single_match = re.search(r'(\d+)', salary_str)
        if single_match:
            salary = int(single_match.group(1))
            return Salary(
                min_salary=salary,
                max_salary=salary,
                currency="USD",
                period="yearly"
            )
        
    except Exception as e:
        logger.warning(f"Error parsing salary '{salary_str}': {e}")
    
    return None

def extract_skills_from_text(text: str) -> list:
    """
    Extract skills from text using keyword matching
    """
    if not text:
        return []
    
    # Common skill keywords
    skill_keywords = [
        'python', 'java', 'javascript', 'typescript', 'react', 'angular', 'vue',
        'node.js', 'express', 'django', 'flask', 'spring', 'sql', 'postgresql',
        'mysql', 'mongodb', 'redis', 'docker', 'kubernetes', 'aws', 'azure',
        'gcp', 'git', 'github', 'gitlab', 'jenkins', 'ci/cd', 'agile', 'scrum',
        'machine learning', 'ai', 'data science', 'analytics', 'tableau', 'power bi',
        'excel', 'r', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'scikit-learn',
        'html', 'css', 'bootstrap', 'sass', 'less', 'webpack', 'babel', 'npm',
        'yarn', 'linux', 'unix', 'bash', 'shell', 'rest api', 'graphql', 'microservices',
        'c++', 'c#', '.net', 'php', 'ruby', 'rails', 'go', 'rust', 'swift', 'kotlin',
        'android', 'ios', 'mobile', 'web', 'frontend', 'backend', 'full stack',
        'devops', 'sre', 'security', 'cybersecurity', 'blockchain', 'cryptocurrency'
    ]
    
    text_lower = text.lower()
    found_skills = []
    
    for skill in skill_keywords:
        if skill in text_lower:
            found_skills.append(skill)
    
    return found_skills

def determine_job_type(title: str, qualifications: str) -> JobType:
    """
    Determine job type from title and qualifications
    """
    text = (title + ' ' + qualifications).lower()
    
    if any(word in text for word in ['intern', 'internship']):
        return JobType.INTERNSHIP
    elif any(word in text for word in ['contract', 'contractor', 'freelance']):
        return JobType.CONTRACT
    elif any(word in text for word in ['part-time', 'part time']):
        return JobType.PART_TIME
    else:
        return JobType.FULL_TIME

def determine_experience_level(title: str, qualifications: str) -> ExperienceLevel:
    """
    Determine experience level from title and qualifications
    """
    text = (title + ' ' + qualifications).lower()
    
    if any(word in text for word in ['senior', 'lead', 'principal', 'staff', 'architect']):
        return ExperienceLevel.SENIOR
    elif any(word in text for word in ['mid', 'intermediate', 'experienced']):
        return ExperienceLevel.MID
    elif any(word in text for word in ['executive', 'director', 'vp', 'vice president', 'c-level']):
        return ExperienceLevel.EXECUTIVE
    else:
        return ExperienceLevel.ENTRY

# Flexible helper functions for generalized CSV processing
def extract_text_field(row: pd.Series, possible_columns: list) -> str:
    """Extract text field from row using possible column names"""
    for col in possible_columns:
        if col in row and pd.notna(row[col]):
            return str(row[col]).strip()
    return ""

def extract_location_flexible(row: pd.Series) -> Location:
    """Extract location information with flexible field mapping"""
    # Try separate city/state/country fields first
    city = extract_text_field(row, ['city', 'location_city', 'job_city', 'work_city'])
    state = extract_text_field(row, ['state', 'location_state', 'job_state', 'work_state'])
    country = extract_text_field(row, ['country', 'location_country', 'job_country', 'work_country'])
    
    # Default to USA if no country specified
    if not country:
        country = "USA"
    
    # Try combined location fields
    if not city and not state:
        location_str = extract_text_field(row, [
            'location', 'Location', 'job_location', 'work_location', 'address', 'work_address'
        ])
        if location_str:
            city, state = parse_location_string(location_str)
    
    return Location(
        city=city or "Unknown",
        state=state or "Unknown",
        country=country
    )

def extract_salary_flexible(row: pd.Series) -> Optional[Salary]:
    """Extract salary information with flexible field mapping"""
    min_salary = extract_numeric_field(row, [
        'min_salary', 'salary_min', 'minimum_salary', 'salary_low', 'low_salary'
    ])
    max_salary = extract_numeric_field(row, [
        'max_salary', 'salary_max', 'maximum_salary', 'salary_high', 'high_salary'
    ])
    
    # Try combined salary field
    if not min_salary and not max_salary:
        salary_str = extract_text_field(row, [
            'salary', 'Salary', 'compensation', 'pay', 'wage', 'salary_range'
        ])
        if salary_str:
            min_salary, max_salary = parse_salary_range(salary_str)
    
    min_salary = min_salary if min_salary and min_salary > 0 else None
    max_salary = max_salary if max_salary and max_salary > 0 else None

    if min_salary or max_salary:
        return Salary(
            min_salary=min_salary,
            max_salary=max_salary,
            currency="USD",
            period="yearly"
        )
    
    return None

def extract_numeric_field(row: pd.Series, possible_columns: list) -> Optional[int]:
    """Extract numeric field from row"""
    for col in possible_columns:
        if col in row and pd.notna(row[col]):
            try:
                value = str(row[col]).replace(',', '').replace('$', '').strip()
                return int(float(value))
            except (ValueError, TypeError):
                continue
    return None

def extract_skills_flexible(row: pd.Series) -> list:
    """Extract skills with flexible field mapping"""
    skills = []
    
    # Try different skill-related columns
    skill_columns = [
        'skills', 'required_skills', 'preferred_skills', 'technologies', 'tech_stack',
        'programming_languages', 'languages', 'tools', 'frameworks', 'technologies_required',
        'technical_skills', 'competencies', 'expertise'
    ]
    
    for col in skill_columns:
        skills_str = extract_text_field(row, [col])
        if skills_str:
            skill_list = re.split(r'[,;|\n]', skills_str)
            for skill in skill_list:
                skill = skill.strip().lower()
                if skill and len(skill) > 1:
                    skills.append(skill)
    
    # Extract skills from description
    description = extract_text_field(row, [
        'description', 'job_description', 'summary', 'details', 'qualifications'
    ])
    if description:
        extracted_skills = extract_skills_from_text(description)
        skills.extend(extracted_skills)
    
    # Remove duplicates and return
    return list(set(skills))

def determine_job_type_flexible(title: str, description: str) -> JobType:
    """Determine job type with flexible text analysis"""
    text = (title + ' ' + description).lower()
    
    if any(word in text for word in ['intern', 'internship']):
        return JobType.INTERNSHIP
    elif any(word in text for word in ['contract', 'contractor', 'freelance', 'consultant']):
        return JobType.CONTRACT
    elif any(word in text for word in ['part-time', 'part time', 'parttime']):
        return JobType.PART_TIME
    else:
        return JobType.FULL_TIME

def determine_experience_level_flexible(title: str, description: str) -> ExperienceLevel:
    """Determine experience level with flexible text analysis"""
    text = (title + ' ' + description).lower()
    
    if any(word in text for word in ['senior', 'lead', 'principal', 'staff', 'architect', 'expert']):
        return ExperienceLevel.SENIOR
    elif any(word in text for word in ['mid', 'intermediate', 'experienced', 'level 2', 'level ii']):
        return ExperienceLevel.MID
    elif any(word in text for word in ['executive', 'director', 'vp', 'vice president', 'c-level', 'head of']):
        return ExperienceLevel.EXECUTIVE
    elif any(word in text for word in ['junior', 'entry', 'entry-level', 'new grad', 'graduate', 'trainee']):
        return ExperienceLevel.ENTRY
    else:
        return ExperienceLevel.ENTRY

def parse_salary_range(salary_str: str) -> tuple:
    """Parse salary range from string"""
    try:
        # Remove currency symbols and clean up
        salary_str = salary_str.replace('$', '').replace(',', '').strip()
        if not salary_str or salary_str.lower() in {"0", "0.0", "none", "nan", "n/a", "na", "not specified"}:
            return None, None
        
        # Look for range pattern (e.g., "74000-138000 /yr")
        range_match = re.search(r'(\d+)-(\d+)', salary_str)
        if range_match:
            min_salary = int(range_match.group(1))
            max_salary = int(range_match.group(2))
            if min_salary <= 0 and max_salary <= 0:
                return None, None
            return min_salary, max_salary
        
        # Look for single number
        single_match = re.search(r'(\d+)', salary_str)
        if single_match:
            salary = int(single_match.group(1))
            if salary <= 0:
                return None, None
            return salary, salary
        
    except Exception as e:
        logger.warning(f"Error parsing salary range '{salary_str}': {e}")
    
    return None, None

def extract_boolean_field(row: pd.Series, possible_columns: list) -> bool:
    """Extract boolean field from row"""
    field_str = extract_text_field(row, possible_columns)
    
    if field_str:
        field_str = field_str.lower().strip()
        return field_str in ['true', 'yes', '1', 'y', 'on']
    
    return False

def parse_location_string(location_str: str) -> tuple:
    """Parse location string to extract city and state"""
    if not location_str or location_str == 'nan':
        return "Unknown", "Unknown"
    
    # Remove quotes and clean up
    location_str = location_str.strip('"').strip()
    
    # Split by comma
    parts = [part.strip() for part in location_str.split(',')]
    
    if len(parts) >= 2:
        city = parts[0]
        state = parts[1]
    else:
        # Try to extract state from single part
        words = location_str.split()
        if len(words) >= 2:
            city = ' '.join(words[:-1])
            state = words[-1]
        else:
            city = location_str
            state = "Unknown"
    
    return city, state

async def process_jobs_in_batches(
    jobs: list,
    index_to_elasticsearch: bool,
    create_neo4j_nodes: bool,
    batch_size: int
) -> Dict[str, Any]:
    """Process jobs in batches"""
    elasticsearch_count = 0
    neo4j_count = 0
    errors = []
    
    # Process in batches
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(jobs) + batch_size - 1)//batch_size}")
        
        # Index to Elasticsearch
        if index_to_elasticsearch:
            try:
                for job in batch:
                    success = es_service.index_job(job)
                    if success:
                        elasticsearch_count += 1
            except Exception as e:
                error_msg = f"Error indexing batch to Elasticsearch: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Create Neo4j nodes
        if create_neo4j_nodes:
            try:
                for job in batch:
                    success = kg_service.create_job_node(job)
                    if success:
                        neo4j_count += 1
                        
                        # Create related nodes
                        kg_service.create_company_node(job.company_name, {})
                        kg_service.create_location_node(job.location)
                        
                        # Create skill nodes and relationships
                        for skill in job.required_skills:
                            kg_service.create_skill_node(skill)
                            kg_service.create_job_skill_relationship(job.id, skill)
                        
                        # Create relationships
                        kg_service.create_job_company_relationship(job.id, job.company_name)
                        location_id = f"{job.location.city}_{job.location.state}_{job.location.country}"
                        kg_service.create_job_location_relationship(job.id, location_id)
                        
            except Exception as e:
                error_msg = f"Error creating Neo4j nodes for batch: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
    
    return {
        "elasticsearch_count": elasticsearch_count,
        "neo4j_count": neo4j_count,
        "errors": errors
    }
