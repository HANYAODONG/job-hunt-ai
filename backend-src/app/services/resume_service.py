import PyPDF2
import docx
from typing import Dict, Any, Optional, List
import logging
import os
import aiofiles
from datetime import datetime
from ..models.candidate import Candidate, CandidateProfile, ResumeUpload
from .nlp_service import NLPService
from .knowledge_graph_service import KnowledgeGraphService

logger = logging.getLogger(__name__)

class ResumeService:
    def __init__(self):
        self.nlp_service = NLPService()
        self.kg_service = KnowledgeGraphService()
        self.upload_dir = "uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
    
    async def process_resume_file(
        self, 
        file_path: str, 
        candidate_id: str
    ) -> CandidateProfile:
        """Process uploaded resume file and extract candidate information"""
        try:
            # Extract text from file
            text = await self._extract_text_from_file(file_path)
            
            # Extract candidate profile using NLP
            profile_data = self.nlp_service.extract_candidate_profile(text)
            
            # Create candidate object
            candidate = self._create_candidate_from_profile(
                profile_data, candidate_id, file_path
            )
            
            # Create candidate node in knowledge graph
            self.kg_service.create_candidate_node(candidate)
            
            # Create candidate profile
            candidate_profile = CandidateProfile(
                candidate=candidate,
                extracted_skills=profile_data["skills"],
                extracted_experience=[exp.get("title", "") for exp in profile_data["experience"]],
                skill_categories=self._categorize_skills(profile_data["skills"]),
                experience_summary=self._create_experience_summary(profile_data["experience"])
            )
            
            return candidate_profile
            
        except Exception as e:
            logger.error(f"Error processing resume file: {e}")
            raise

    def parse_resume_text(self, text: str, mode: str = "enhanced") -> Dict[str, Any]:
        """Parse raw resume text with either baseline spaCy NER or enhanced pipeline."""
        try:
            mode = (mode or "enhanced").lower()
            if mode == "spacy":
                return self._parse_with_spacy(text)
            return self._parse_with_enhanced(text)
        except Exception as e:
            logger.error(f"Error parsing resume text: {e}")
            return {}

    def _parse_with_spacy(self, text: str) -> Dict[str, Any]:
        """Lightweight extraction relying mostly on spaCy entities."""
        profile = {
            "name": "",
            "email": "",
            "skills": [],
            "education": [],
            "experience": []
        }

        doc = None
        if self.nlp_service.nlp:
            doc = self.nlp_service.nlp(text)

        if doc:
            person_ents = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
            if person_ents:
                profile["name"] = person_ents[0]
            # crude skill list: top nouns/proper nouns
            profile["skills"] = list({token.text for token in doc if token.pos_ in {"NOUN", "PROPN"} and token.is_alpha})[:20]
            education_sents = [sent.text.strip() for sent in doc.sents if any(keyword in sent.text.lower() for keyword in ["university", "college", "bachelor", "master", "phd", "degree"])]
            profile["education"] = education_sents
            experience_sents = [sent.text.strip() for sent in doc.sents if any(keyword in sent.text.lower() for keyword in ["experience", "worked", "managed", "engineer", "developer", "designer"])]
            profile["experience"] = experience_sents

        email = self._extract_emails_simple(text)
        profile["email"] = email[0] if email else ""
        return profile

    def _parse_with_enhanced(self, text: str) -> Dict[str, Any]:
        """Use the richer NLP pipeline for full extraction."""
        enhanced = self.nlp_service.extract_candidate_profile(text)
        return {
            "name": enhanced.get("name"),
            "email": (enhanced.get("contact_info") or {}).get("emails", [None])[0],
            "skills": enhanced.get("skills", []),
            "education": enhanced.get("education", []),
            "experience": enhanced.get("experience", []),
        }

    def _extract_emails_simple(self, text: str) -> List[str]:
        """Simple regex email extraction."""
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(email_pattern, text)
    
    async def _extract_text_from_file(self, file_path: str) -> str:
        """Extract text from various file formats"""
        try:
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.pdf':
                return self._extract_text_from_pdf(file_path)
            elif file_extension in ['.doc', '.docx']:
                return self._extract_text_from_docx(file_path)
            elif file_extension == '.txt':
                return await self._extract_text_from_txt(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
                
        except Exception as e:
            logger.error(f"Error extracting text from file: {e}")
            raise
    
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise
    
    def _extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from DOCX: {e}")
            raise
    
    async def _extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file"""
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                return await file.read()
        except Exception as e:
            logger.error(f"Error extracting text from TXT: {e}")
            raise
    
    def _create_candidate_from_profile(
        self, 
        profile_data: Dict[str, Any], 
        candidate_id: str, 
        file_path: str
    ) -> Candidate:
        """Create Candidate object from extracted profile data"""
        try:
            # Extract contact information
            contact_info = profile_data.get("contact_info", {})
            emails = contact_info.get("emails", [])
            phones = contact_info.get("phones", [])
            locations = contact_info.get("locations", [])
            
            # Create skills list
            skills = []
            for skill_name in profile_data.get("skills", []):
                skills.append({
                    "name": skill_name,
                    "level": "intermediate",  # Default level
                    "category": "technical"
                })
            
            # Create experience list
            experience = []
            for exp in profile_data.get("experience", []):
                experience.append({
                    "company": exp.get("company", "Unknown"),
                    "position": exp.get("title", "Unknown Position"),
                    "start_date": datetime.now().isoformat(),  # Default date
                    "end_date": None,
                    "description": exp.get("description", ""),
                    "skills_used": [],
                    "achievements": []
                })
            
            # Create education list
            education = []
            for edu in profile_data.get("education", []):
                education.append({
                    "institution": edu.get("institution", "Unknown"),
                    "degree": edu.get("degree", "Unknown Degree"),
                    "field_of_study": "Unknown",
                    "graduation_date": None,
                    "gpa": None
                })
            
            candidate = Candidate(
                id=candidate_id,
                name=profile_data.get("name", "Name Not Found"),  # Use extracted name
                email=emails[0] if emails else "",
                phone=phones[0] if phones else None,
                location=locations[0] if locations else None,
                summary=profile_data.get("summary", ""),
                skills=skills,
                experience=experience,
                education=education,
                certifications=[],
                languages=[],
                visa_status=None,
                availability=None,
                salary_expectation=None,
                preferred_locations=locations,
                resume_file_path=file_path,
                years_experience=profile_data.get("years_experience"),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            return candidate
            
        except Exception as e:
            logger.error(f"Error creating candidate from profile: {e}")
            raise
    
    def _categorize_skills(self, skills: List[str]) -> Dict[str, List[str]]:
        """Categorize skills into different categories"""
        categories = {
            "programming_languages": [],
            "frameworks": [],
            "databases": [],
            "cloud_platforms": [],
            "tools": [],
            "methodologies": [],
            "soft_skills": [],
            "other": []
        }
        
        # Define skill categories
        skill_categories = {
            "programming_languages": [
                "python", "java", "javascript", "c++", "c#", "go", "rust", 
                "swift", "kotlin", "php", "ruby", "scala", "typescript"
            ],
            "frameworks": [
                "react", "angular", "vue", "node.js", "express", "django", 
                "flask", "fastapi", "spring", "laravel", "rails", "tensorflow", "pytorch"
            ],
            "databases": [
                "sql", "postgresql", "mysql", "mongodb", "redis", 
                "elasticsearch", "cassandra", "oracle"
            ],
            "cloud_platforms": [
                "aws", "azure", "gcp", "google cloud", "amazon web services"
            ],
            "tools": [
                "docker", "kubernetes", "jenkins", "git", "github", "gitlab",
                "jira", "confluence", "slack", "figma", "photoshop"
            ],
            "methodologies": [
                "agile", "scrum", "kanban", "tdd", "bdd", "devops", "ci/cd"
            ],
            "soft_skills": [
                "leadership", "communication", "teamwork", "problem solving",
                "project management", "mentoring", "presentation"
            ]
        }
        
        for skill in skills:
            skill_lower = skill.lower()
            categorized = False
            
            for category, keywords in skill_categories.items():
                if any(keyword.casefold() == skill_lower.casefold() for keyword in keywords):
                    categories[category].append(skill)
                    categorized = True
                    break
            
            if not categorized:
                categories["other"].append(skill)
        
        return categories
    
    def _create_experience_summary(self, experience: List[Dict[str, Any]]) -> str:
        """Create a summary of work experience"""
        if not experience:
            return "No work experience found in resume."
        
        summary_parts = []
        for exp in experience:
            title = exp.get("title", "Unknown Position")
            company = exp.get("company", "Unknown Company")
            description = exp.get("description", "")
            
            summary_parts.append(f"{title} at {company}")
            if description:
                summary_parts.append(f" - {description[:100]}...")
        
        return " | ".join(summary_parts)
    
    async def save_uploaded_file(
        self, 
        file_content: bytes, 
        filename: str, 
        candidate_id: str
    ) -> ResumeUpload:
        """Save uploaded resume file"""
        try:
            # Ensure upload directory exists
            os.makedirs(self.upload_dir, exist_ok=True)
            
            # Create unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(filename)[1]
            unique_filename = f"{candidate_id}_{timestamp}{file_extension}"
            file_path = os.path.join(self.upload_dir, unique_filename)
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as file:
                await file.write(file_content)
            
            # Create upload record
            upload = ResumeUpload(
                file_name=unique_filename,
                file_size=len(file_content),
                file_type=file_extension,
                upload_date=datetime.now()
            )
            
            return upload
            
        except Exception as e:
            logger.error(f"Error saving uploaded file: {e}")
            raise
    
    def get_resume_insights(self, candidate_profile: CandidateProfile) -> Dict[str, Any]:
        """Get insights about the candidate's resume"""
        try:
            insights = {
                "skill_analysis": {
                    "total_skills": len(candidate_profile.extracted_skills),
                    "skill_categories": candidate_profile.skill_categories,
                    "top_skills": candidate_profile.extracted_skills[:10]
                },
                "experience_analysis": {
                    "total_experience": len(candidate_profile.extracted_experience),
                    "experience_summary": candidate_profile.experience_summary,
                    "career_progression": self._analyze_career_progression(candidate_profile.extracted_experience)
                },
                "marketability_score": self._calculate_marketability_score(candidate_profile),
                "improvement_suggestions": self._get_improvement_suggestions(candidate_profile)
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting resume insights: {e}")
            return {}
    
    def _analyze_career_progression(self, experience: List[str]) -> Dict[str, Any]:
        """Analyze career progression from experience"""
        # This is a simplified analysis - in practice, you'd use more sophisticated NLP
        progression = {
            "has_progression": len(experience) > 1,
            "experience_levels": [],
            "industry_consistency": True,  # Simplified
            "leadership_roles": []
        }
        
        # Look for leadership indicators
        leadership_keywords = ["manager", "director", "lead", "senior", "principal", "architect"]
        for exp in experience:
            if any(keyword in exp.lower() for keyword in leadership_keywords):
                progression["leadership_roles"].append(exp)
        
        return progression
    
    def _calculate_marketability_score(self, candidate_profile: CandidateProfile) -> float:
        """Calculate a marketability score for the candidate"""
        try:
            score = 0.0
            
            # Skill diversity (0-30 points)
            skill_categories = candidate_profile.skill_categories
            category_count = len([cat for cat in skill_categories.values() if cat])
            score += min(category_count * 5, 30)
            
            # Experience depth (0-25 points)
            experience_count = len(candidate_profile.extracted_experience)
            score += min(experience_count * 5, 25)
            
            # Technical skills (0-25 points)
            tech_skills = len(skill_categories.get("programming_languages", []) + 
                            skill_categories.get("frameworks", []) + 
                            skill_categories.get("databases", []))
            score += min(tech_skills * 3, 25)
            
            # Soft skills (0-20 points)
            soft_skills = len(skill_categories.get("soft_skills", []))
            score += min(soft_skills * 4, 20)
            
            return min(score, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating marketability score: {e}")
            return 0.0
    
    def _get_improvement_suggestions(self, candidate_profile: CandidateProfile) -> List[str]:
        """Get suggestions for improving the resume"""
        suggestions = []
        
        # Check for missing elements
        if not candidate_profile.candidate.summary:
            suggestions.append("Add a professional summary to highlight your key strengths")
        
        if len(candidate_profile.extracted_skills) < 5:
            suggestions.append("Include more technical skills to improve job matching")
        
        if not candidate_profile.candidate.education:
            suggestions.append("Add education information if applicable")
        
        # Check skill categories
        skill_categories = candidate_profile.skill_categories
        if not skill_categories.get("programming_languages"):
            suggestions.append("Consider adding programming languages to your skills")
        
        if not skill_categories.get("soft_skills"):
            suggestions.append("Include soft skills like communication and teamwork")
        
        return suggestions
