from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
import os
import logging
import re
import numpy as np
from ..core.config import settings

try:
    import spacy
except ImportError:  # pragma: no cover - optional dependency
    spacy = None

try:
    import nltk
except ImportError:  # pragma: no cover - optional dependency
    nltk = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None

try:
    from sklearn.feature_extraction.text import HashingVectorizer
except ImportError:  # pragma: no cover - optional dependency
    HashingVectorizer = None

try:
    from textblob import TextBlob
except ImportError:  # pragma: no cover - optional dependency
    TextBlob = None

logger = logging.getLogger(__name__)
_CANONICAL_VOCABULARY: Optional[List[str]] = None

_RESUME_SECTION_HEADINGS = {
    "个人简历", "基本信息", "个人概述", "教育背景", "技能栈", "技术栈",
    "专业技能", "核心技能", "工作经历", "项目经历", "综合能力",
    "证书", "认证", "联系方式", "求职意向", "自我评价", "获奖经历",
    "技能", "skills", "technical skills", "experience", "employment",
    "work experience", "projects", "project experience", "education",
    "summary", "profile", "contact", "certifications",
}


def _load_canonical_vocabulary() -> List[str]:
    """Load the reviewed v2 skill vocabulary once; no model download required."""
    global _CANONICAL_VOCABULARY
    if _CANONICAL_VOCABULARY is not None:
        return _CANONICAL_VOCABULARY
    root = Path(os.getenv("JOB_HUNT_REPO_ROOT", Path(__file__).resolve().parents[3]))
    path = root / "artifacts" / "canonical_role_pool_v2" / "canonical_jobs.jsonl"
    values: set[str] = set()
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for value in row.get("required_skills") or row.get("skills") or []:
                    value = str(value).strip()
                    if 1 < len(value) <= 40:
                        values.add(value)
    except OSError:
        values = set()
    _CANONICAL_VOCABULARY = sorted(values, key=lambda value: (-len(value), value.casefold()))
    return _CANONICAL_VOCABULARY

class NLPService:
    def __init__(self, sentence_transformer_model: Optional[str] = None):
        self.nlp = None
        self.sentence_transformer = None
        self.sentence_transformer_model = sentence_transformer_model or settings.SENTENCE_TRANSFORMER_MODEL
        self.fallback_vectorizer = (
            HashingVectorizer(analyzer="char", ngram_range=(2, 4), n_features=768, alternate_sign=False, norm=None)
            if HashingVectorizer
            else None
        )
        self.setup_models()

    @property
    def active_embedding_model_name(self) -> str:
        """Return the embedding implementation that is actually serving requests."""
        if self.sentence_transformer is not None:
            return self.sentence_transformer_model
        if self.fallback_vectorizer is not None:
            return "char-ngram-hashing-768"
        return "unavailable"
    
    def setup_models(self):
        """Initialize NLP models"""
        try:
            if not settings.ENABLE_SPACY_MODEL:
                logger.info("spaCy model loading disabled; using rule-based NLP fallbacks.")
            elif spacy:
                try:
                    self.nlp = spacy.load(settings.SPACY_MODEL)
                    logger.info(f"Loaded spaCy model: {settings.SPACY_MODEL}")
                except Exception as exc:  # pragma: no cover - spaCy optional
                    logger.warning(f"Failed to load spaCy model '{settings.SPACY_MODEL}': {exc}")
                    self.nlp = None
            else:
                logger.warning("spaCy is not installed; NLP entity extraction disabled.")
            
            if not settings.ENABLE_SENTENCE_TRANSFORMER:
                logger.info("Sentence transformer loading disabled; using deterministic embedding fallback.")
            elif SentenceTransformer:
                try:
                    self.sentence_transformer = SentenceTransformer(self.sentence_transformer_model)
                    logger.info(f"Loaded sentence transformer: {self.sentence_transformer_model}")
                except Exception as exc:  # pragma: no cover - optional
                    logger.warning(f"Failed to load sentence transformer '{self.sentence_transformer_model}': {exc}")
                    self.sentence_transformer = None
            else:
                logger.warning("sentence-transformers is not installed; semantic embeddings disabled.")
            
            if nltk:
                try:
                    nltk.data.find('tokenizers/punkt')
                except LookupError:
                    logger.warning("NLTK punkt not available; skipping download to avoid blocking startup.")
                
                try:
                    nltk.data.find('corpora/stopwords')
                except LookupError:
                    logger.warning("NLTK stopwords not available; skipping download to avoid blocking startup.")
            else:
                logger.warning("NLTK is not installed; skipping tokenizer/stopword downloads.")
                
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Error setting up NLP models: {e}")
    
    def extract_entities_from_text(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from text using spaCy"""
        if not self.nlp or not text or not text.strip():
            return {}
        
        try:
            doc = self.nlp(text)
            entities = {
                "PERSON": [],
                "ORG": [],
                "GPE": [],  # Geopolitical entities (countries, cities, states)
                "MONEY": [],
                "DATE": [],
                "TIME": [],
                "PERCENT": [],
                "CARDINAL": [],
                "ORDINAL": [],
                "NORP": [],  # Nationalities, religious, or political groups
                "FAC": [],   # Buildings, airports, highways, bridges
                "LOC": [],   # Non-GPE locations
                "PRODUCT": [],
                "EVENT": [],
                "WORK_OF_ART": [],
                "LAW": [],
                "LANGUAGE": [],
                "MISC": []
            }
            
            for ent in doc.ents:
                if ent.label_ in entities:
                    entities[ent.label_].append(ent.text.strip())
            
            # Remove duplicates while preserving order
            for key in entities:
                entities[key] = list(dict.fromkeys(entities[key]))
            
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return {}
    
    def extract_skills_from_text(self, text: str) -> List[str]:
        """Extract normalized technical skills with deterministic evidence.

        The legacy regular expressions remain as a lightweight fallback. The
        shared evidence dictionary adds Chinese skills, aliases and newer
        frameworks while retaining source-text evidence for every match.
        """
        # PDF layout can split a token across lines (``Py\nthon``). Repair
        # only terms that already exist in the reviewed local vocabulary.
        text = self._repair_split_skill_tokens(text or "")

        # Common technical skills patterns
        skill_patterns = [
            r'\b(?:Python|Java|JavaScript|C\+\+|C#|Go|Rust|Swift|Kotlin|PHP|Ruby|Scala|TypeScript)\b',
            r'\b(?:React|Angular|Vue|Node\.?js|Express|Django|Flask|Spring|Laravel|Rails)\b',
            r'\b(?:AWS|Azure|GCP|Docker|Kubernetes|Jenkins|Git|GitHub|GitLab)\b',
            r'\b(?:SQL|PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch|Cassandra)\b',
            r'\b(?:Machine Learning|ML|AI|Deep Learning|NLP|Computer Vision|TensorFlow|PyTorch|Scikit-learn)\b',
            r'\b(?:Data Science|Analytics|Pandas|NumPy|Matplotlib|Seaborn|Jupyter)\b',
            r'\b(?:DevOps|CI/CD|Microservices|REST|GraphQL|API|Web Services)\b',
            r'\b(?:Agile|Scrum|Kanban|TDD|BDD|Unit Testing|Integration Testing)\b',
            r'\b(?:Linux|Unix|Windows|macOS|Bash|Shell|PowerShell)\b',
            r'\b(?:HTML|CSS|SASS|LESS|Bootstrap|Tailwind|Material UI)\b'
        ]
        
        skills = set()
        text_lower = text.lower()
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            skills.update(matches)

        # Lightweight bilingual vocabulary for resumes whose skills are written
        # in Chinese or wrapped across PDF lines. This avoids requiring a large
        # embedding model just to recover explicit evidence.
        extended_terms = (
            "大模型,大语言模型,机器学习,深度学习,计算机视觉,自然语言处理,推荐算法,广告算法,搜索算法,"
            "风控算法,数据挖掘,数据工程,数据平台,数据治理,数据分析,数据科学,数据仓库,数据库,"
            "后端开发,前端开发,全栈开发,客户端开发,嵌入式,驱动开发,系统软件,软件架构,"
            "自动驾驶,机器人,导航定位,控制算法,芯片设计,芯片验证,芯片测试,FPGA,硬件设计,"
            "网络安全,安全运营,安全合规,云计算,运维,DevOps,测试开发,软件测试,质量工程,"
            "产品经理,数据产品,技术产品,项目管理,用户研究,交互设计,视觉设计,原型设计,UI/UX,"
            "Python,Java,JavaScript,TypeScript,Go,Rust,C/C++,SQL,HTML,CSS,React,Vue,Node.js,"
            "Spring,Spring Boot,Django,Flask,FastAPI,LangChain,Agent,RAG,Prompt工程,PyTorch,TensorFlow,"
            "Kubernetes,Docker,Linux,Git,MySQL,PostgreSQL,Redis,Kafka,Elasticsearch,PowerShell"
        ).split(",")
        for term in extended_terms:
            if term.casefold() in text_lower:
                skills.add(term)

        # Reuse the canonical v2 JD vocabulary for Chinese/domain-specific
        # skills (embedded, hardware, thermal, security, etc.). This is a
        # dictionary lookup over local artifacts, not a heavyweight model.
        for term in _load_canonical_vocabulary():
            if term.casefold() in text_lower:
                skills.add(term)
        
        # Extract skills using spaCy NER and POS tagging
        if self.nlp:
            doc = self.nlp(text)
            for token in doc:
                # Look for technical terms (nouns, proper nouns)
                if (token.pos_ in ['NOUN', 'PROPN'] and 
                    len(token.text) > 2 and 
                    not token.is_stop and
                    not token.is_punct):
                    
                    # Check if it looks like a technical skill
                    if self._is_technical_skill(token.text):
                        skills.add(token.text)
        
        try:
            from .skill_evidence_service import extract_skills_with_evidence

            evidence = extract_skills_with_evidence(text)
            skills.update(item["skill"] for item in evidence["skills"])
        except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Evidence-based skill extraction unavailable: %s", exc)

        return sorted(skills, key=lambda item: (item.casefold(), item))
    
    def _is_technical_skill(self, text: str) -> bool:
        """Check if a text looks like a technical skill"""
        # Simple heuristics to identify technical skills
        technical_indicators = [
            'api', 'sdk', 'framework', 'library', 'tool', 'platform',
            'database', 'server', 'cloud', 'mobile', 'web', 'desktop',
            'algorithm', 'data structure', 'pattern', 'architecture',
            'protocol', 'standard', 'specification', 'methodology'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in technical_indicators)
    
    def extract_job_requirements(self, text: str) -> Dict[str, List[str]]:
        """Extract job requirements from job description"""
        requirements = {
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "qualifications": [],
            "benefits": [],
            "location": "",
            "salary_range": "",
            "experience_level": "",
            "education": ""
        }
        
        # Split text into sections
        sections = self._split_job_description(text)
        
        for section_name, section_text in sections.items():
            if "requirement" in section_name.lower() or "qualification" in section_name.lower():
                skills = self.extract_skills_from_text(section_text)
                if "required" in section_name.lower():
                    requirements["required_skills"].extend(skills)
                else:
                    requirements["preferred_skills"].extend(skills)
                requirements["qualifications"].append(section_text)
            
            elif "responsibilit" in section_name.lower():
                requirements["responsibilities"].append(section_text)
            
            elif "benefit" in section_name.lower():
                requirements["benefits"].append(section_text)
            
            elif "location" in section_name.lower():
                requirements["location"] = section_text
            
            elif "salary" in section_name.lower() or "compensation" in section_name.lower():
                requirements["salary_range"] = section_text
        
        # Extract entities for additional information
        entities = self.extract_entities_from_text(text)
        
        # Extract location from entities
        if entities.get("GPE"):
            requirements["location"] = ", ".join(entities["GPE"])
        
        # Extract salary from entities
        if entities.get("MONEY"):
            requirements["salary_range"] = ", ".join(entities["MONEY"])
        
        if not requirements["required_skills"] and not requirements["preferred_skills"]:
            requirements["required_skills"] = self.extract_skills_from_text(text)
        requirements["required_skills"] = list(dict.fromkeys(requirements["required_skills"]))
        requirements["preferred_skills"] = list(dict.fromkeys(requirements["preferred_skills"]))
        return requirements

    def extract_hard_constraints(self, text: str) -> Dict[str, Any]:
        """Extract hard eligibility constraints from job description.

        Heuristic-based extraction for:
        - visa/work authorization
        - location/remote eligibility
        - must-have certifications
        - minimum degree/degree-type
        - minimum years of experience
        - security clearance
        - language fluency
        - legal/licensure requirements
        """
        constraints: Dict[str, Any] = {
            "requires_us_work_auth": False,
            "no_visa_sponsorship": False,
            "remote_allowed": None,
            "location_required": None,  # free text city/state/country if enforced
            "must_have_certifications": [],
            "min_degree": None,
            "min_years_experience": None,
            "security_clearance": None,
            "language_requirements": [],
            "licensure_requirements": []
        }

        if not text:
            return constraints

        t = text.lower()

        # Visa / work authorization (broader phrasing)
        visa_required_patterns = [
            r"\b(us|united states) work authorization required\b",
            r"\bmust be authorized to work in the (us|united states)\b",
            r"\b(legally|lawfully) authorized to work\b",
            r"\b(work authorization)\b"
        ]
        if any(re.search(p, t) for p in visa_required_patterns):
            constraints["requires_us_work_auth"] = True
        if re.search(r"\b(no\s+visa\s+sponsorship|without\s+sponsorship|unable\s+to\s+sponsor|sponsorship\s+not\s+available)\b", t):
            constraints["no_visa_sponsorship"] = True

        # Remote / location (more variants)
        if re.search(r"\b(remote[-\s]?first|remote\s+friendly|open\s+to\s+remote|hybrid)\b", t):
            constraints["remote_allowed"] = True
        if re.search(r"\b(on[-\s]?site\s+only|must\s+be\s+on[-\s]?site|no\s+remote|not\s+remote)\b", t):
            constraints["remote_allowed"] = False
        # Rough location extraction
        loc_match = re.search(r"\b(located in|based in|work in|onsite in|on[-\s]?site in)\s+([A-Za-z\s,]+)\b", t)
        if loc_match:
            constraints["location_required"] = loc_match.group(2).strip()

        # Certifications (common examples)
        cert_patterns = [
            r"aws\s+certified\s+(solutions\s+architect|developer|sysops|devops\s+engineer)",
            r"pmp\b",
            r"prince2\b",
            r"cissp\b",
            r"security\+\b",
            r"network\+\b",
            r"ccna\b|ccnp\b",
            r"az-?900\b|dp-?900\b|ai-?900\b|az-?104\b|az-?305\b",
            r"gcp\s+professional\s+(architect|engineer)",
            r"ckad\b|cka\b|cks\b",
            r"\bcompTIA\b\s*(?:A\+|Network\+|Security\+)"
        ]
        found_certs = []
        for pat in cert_patterns:
            for m in re.findall(pat, t, re.IGNORECASE):
                if isinstance(m, tuple):
                    found_certs.append(" ".join([x for x in m if x]).strip())
                else:
                    found_certs.append(m if isinstance(m, str) else str(m))
        # Normalize
        constraints["must_have_certifications"] = list(dict.fromkeys([c.upper() for c in found_certs]))

        # Minimum degree
        degree_map = [
            (r"doctorate|phd|d\.phil|ph\.d", "doctorate"),
            (r"master\b|m\.?sc\b|m\.?eng\b|ms\b|m\.s\.", "master"),
            (r"bachelor\b|b\.?sc\b|b\.?eng\b|bs\b|ba\b|b\.s\.|b\.a\.", "bachelor"),
            (r"associate\b|a\.?a\.?|a\.?s\.?", "associate")
        ]
        for pat, level in degree_map:
            # minimum/required OR phrases like "X degree in ... required"
            if re.search(rf"((minimum|required)\s+({pat}))|(({pat}).{0,20}\s+required)", t):
                constraints["min_degree"] = level
                break

        # Minimum years experience
        yrs = re.findall(r"(minimum|required|at\s+least)\s+(\d{1,2})\s+years?\s+(of\s+)?(relevant|professional|industry|experience)", t)
        if yrs:
            try:
                constraints["min_years_experience"] = int(yrs[0][1])
            except Exception:
                pass
        else:
            # Alternate pattern: "\d+\+ years"
            yrs2 = re.findall(r"(\d{1,2})\+\s+years", t)
            if yrs2:
                try:
                    constraints["min_years_experience"] = int(yrs2[0])
                except Exception:
                    pass

        # Security clearance
        clearance_patterns = [r"secret\s+clearance", r"top\s+secret", r"ts/sci", r"ts\s*/\s*sci", r"public\s+trust", r"dod\s+clearance"]
        for pat in clearance_patterns:
            if re.search(pat, t):
                constraints["security_clearance"] = pat
                break

        # Language requirements
        lang_terms = ["english", "spanish", "mandarin", "japanese", "french", "german", "hindi", "portuguese", "korean", "arabic"]
        langs = []
        for lang in lang_terms:
            if re.search(rf"(fluent|fluency|proficient|native|excellent)\s+in\s+{lang}\b", t):
                langs.append(lang)
            if re.search(rf"{lang}\s+(fluency|required)\b", t):
                langs.append(lang)
        constraints["language_requirements"] = list(dict.fromkeys(langs))

        # Licensure requirements
        lic_patterns = [
            r"bar\s+license|licensed\s+attorney",
            r"cpa\b",
            r"pe\b(\s+license)?|professional\s+engineer",
            r"medical\s+license|state\s+license\s+to\s+practice",
            r"nursing\s+license|rn\b|registered\s+nurse",
            r"pharmacist\s+license|law\s+license|teaching\s+credential"
        ]
        found_lic = []
        for pat in lic_patterns:
            if re.search(pat, t):
                found_lic.append(pat)
        constraints["licensure_requirements"] = found_lic

        return constraints
    
    def _split_job_description(self, text: str) -> Dict[str, str]:
        """Split job description into sections"""
        sections = {}
        
        # Common section headers
        section_patterns = [
            r'(?i)(requirements?|qualifications?|skills?|must have)',
            r'(?i)(responsibilities?|duties?|what you\'ll do)',
            r'(?i)(benefits?|perks?|compensation)',
            r'(?i)(location|where|office)',
            r'(?i)(salary|compensation|pay|wage)',
            r'(?i)(about us|company|who we are)',
            r'(?i)(experience|years?|level)',
            r'(?i)(education|degree|certification)'
        ]
        
        current_section = "general"
        current_text = []
        
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line is a section header
            is_header = False
            for pattern in section_patterns:
                if re.search(pattern, line):
                    # Save previous section
                    if current_text:
                        sections[current_section] = '\n'.join(current_text)
                    
                    # Start new section
                    current_section = line.lower()
                    current_text = []
                    is_header = True
                    break
            
            if not is_header:
                current_text.append(line)
        
        # Save last section
        if current_text:
            sections[current_section] = '\n'.join(current_text)
        
        return sections
    
    def extract_candidate_profile(self, resume_text: str) -> Dict[str, Any]:
        """Extract candidate profile from resume text"""
        profile = {
            "name": "",
            "skills": [],
            "experience": [],
            "education": [],
            "contact_info": {},
            "summary": "",
            "certifications": [],
            "languages": []
        }
        
        # Extract candidate name first (most important)
        profile["name"] = self._extract_candidate_name(resume_text)
        
        # Extract entities
        entities = self.extract_entities_from_text(resume_text)
        
        # Extract contact information
        profile["contact_info"] = {
            "emails": self._extract_emails(resume_text),
            "phones": self._extract_phones(resume_text),
            "locations": entities.get("GPE", [])
        }
        
        # Prefer an explicit skill-list section when one exists. Full-text
        # dictionary matching remains the fallback for unstructured resumes.
        section_skills = self._extract_labeled_skill_section(resume_text)
        profile["skills"] = section_skills or self.extract_skills_from_text(resume_text)
        profile["years_experience"] = self._extract_years_experience(resume_text)
        
        # Extract experience (simplified)
        experience_sections = self._extract_experience_sections(resume_text)
        profile["experience"] = experience_sections
        
        # Extract education
        education_sections = self._extract_education_sections(resume_text)
        profile["education"] = education_sections
        
        return profile

    @staticmethod
    def _extract_labeled_skill_section(text: str) -> List[str]:
        """Extract comma-like delimited skills from an explicit resume field."""
        if not text:
            return []
        text = NLPService._repair_split_skill_tokens(text)
        header_pattern = re.compile(
            r"^\s*(?:技能栈|技术栈|专业技能|核心技能|skills?|technical skills?)\s*(?:[：:]\s*(.*))?$",
            re.IGNORECASE,
        )
        def clean(chunks: List[str]) -> List[str]:
            values = re.split(r"[、,，;；|]+", " ".join(chunks))
            seen: set[str] = set()
            skills: List[str] = []
            for value in values:
                # The complete resume text was repaired once before section
                # parsing; repeating that pass for every token is needlessly
                # expensive on a 100-resume batch.
                skill = value.strip().strip("。.")
                key = skill.casefold()
                if not skill or len(skill) > 40 or key in seen:
                    continue
                if NLPService._is_resume_section_heading(skill):
                    continue
                if any(mark in skill for mark in (
                    "工作经历", "项目经历", "综合能力", "个人概述", "教育背景",
                    "技术栈包括", "累计", "主要覆盖", "能够承担", "负责",
                    "担任", "参与", "围绕", "项目结果", "技术栈",
                )):
                    continue
                if len(skill.split()) > 5:
                    continue
                seen.add(key)
                skills.append(skill)
            return skills

        lines = text.splitlines()
        inline_fallback: List[str] = []
        for index, line in enumerate(lines):
            match = header_pattern.match(line.strip())
            if not match:
                continue
            inline_value = (match.group(1) or "").strip()
            # Prefer a standalone skills section.  Generated and real resumes
            # often mention ``技能栈：...`` inside the summary before the real
            # section; treating that first mention as authoritative truncates
            # the actual list and loses discriminative skills.
            if inline_value:
                if not inline_fallback:
                    inline_fallback = [inline_value]
                continue
            chunks = [""]
            for continuation in lines[index + 1:index + 12]:
                stripped = continuation.strip()
                if not stripped or NLPService._is_resume_section_heading(stripped):
                    break
                chunks.append(stripped)
            result = clean(chunks)
            if result:
                return result
        return clean(inline_fallback) if inline_fallback else []

    @staticmethod
    def _is_resume_section_heading(value: str) -> bool:
        stripped = re.sub(r"\s+", " ", str(value or "").strip()).strip("：:")
        return stripped.casefold() in {item.casefold() for item in _RESUME_SECTION_HEADINGS}

    @staticmethod
    def _repair_split_skill_tokens(text: str) -> str:
        """Join tokens split by PDF line wrapping in linear time.

        A wrap is joined only when neither side is a standalone resume
        heading.  This repairs ``Py\\nthon`` and Chinese terms split across
        lines without the expensive per-vocabulary regex loop.
        """
        if not text:
            return ""
        lines = str(text).splitlines()
        if not lines:
            return str(text)
        merged: List[str] = []
        for line in lines:
            current = line.strip()
            if not merged:
                merged.append(current)
                continue
            previous = merged[-1]
            if (
                previous
                and current
                and not NLPService._is_resume_section_heading(previous)
                and not NLPService._is_resume_section_heading(current)
                and re.search(r"[A-Za-z0-9\u4e00-\u9fff]$", previous)
                and re.match(r"^[A-Za-z0-9\u4e00-\u9fff]", current)
            ):
                merged[-1] = previous + current
            else:
                merged.append(current)
        return "\n".join(merged)

    @staticmethod
    def _extract_years_experience(text: str) -> Optional[int]:
        """Extract an explicitly stated total/minimum experience duration."""
        if not text:
            return None
        patterns = (
            r"(?i)(\d{1,2})\s*\+?\s*years?(?:\s+of)?\s+(?:work\s+|professional\s+|relevant\s+)?experience",
            r"(?i)(?:experience|worked)\s*(?:of|for)?\s*(\d{1,2})\s*\+?\s*years?",
            r"(\d{1,2})\s*年(?:以上|及以上)?[^，。；;\n]{0,20}(?:经验|经历)",
            r"(?:具备|拥有|具有)?\s*(\d{1,2})\s*年(?:以上|及以上)?[^，。；;\n]{0,20}(?:经验|经历)",
        )
        values = []
        for pattern in patterns:
            values.extend(int(value) for value in re.findall(pattern, text) if int(value) <= 50)
        return max(values) if values else None
    
    def _extract_emails(self, text: str) -> List[str]:
        """Extract email addresses from text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(email_pattern, text)
    
    def _extract_phones(self, text: str) -> List[str]:
        """Extract phone numbers from text"""
        phone_patterns = [
            r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',
            r'\+?[0-9]{1,3}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,9}'
        ]
        
        phones = []
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, text))
        
        return phones
    
    def _extract_experience_sections(self, text: str) -> List[Dict[str, str]]:
        """Extract work experience sections from resume"""
        experience = []
        
        # Look for common experience indicators
        exp_patterns = [
            r'(?i)(experience|employment|work history|professional experience)',
            r'(?i)(internship|co-op|volunteer)',
            r'(?i)(project|portfolio)'
        ]
        
        # This is a simplified extraction - in practice, you'd use more sophisticated parsing
        lines = text.split('\n')
        current_exp = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this looks like a job title or company
            if self._looks_like_job_info(line):
                if current_exp:
                    experience.append(current_exp)
                current_exp = {"title": line}
            elif current_exp and "title" in current_exp:
                if "description" not in current_exp:
                    current_exp["description"] = line
                else:
                    current_exp["description"] += " " + line
        
        if current_exp:
            experience.append(current_exp)
        
        return experience
    
    def _looks_like_job_info(self, line: str) -> bool:
        """Check if a line looks like job information"""
        # Simple heuristics
        job_indicators = [
            "engineer", "developer", "analyst", "manager", "director",
            "consultant", "specialist", "coordinator", "assistant",
            "intern", "volunteer", "freelance", "contract"
        ]
        
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in job_indicators)
    
    def _extract_education_sections(self, text: str) -> List[Dict[str, str]]:
        """Extract education sections from resume"""
        education = []
        
        # Look for education indicators
        edu_patterns = [
            r'(?i)(education|academic|degree|university|college|school)',
            r'(?i)(bachelor|master|phd|doctorate|associate|certificate)'
        ]
        
        lines = text.split('\n')
        current_edu = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this looks like education information
            if any(re.search(pattern, line) for pattern in edu_patterns):
                if current_edu:
                    education.append(current_edu)
                current_edu = {"institution": line}
            elif current_edu and "institution" in current_edu:
                if "degree" not in current_edu:
                    current_edu["degree"] = line
                else:
                    current_edu["description"] = line
        
        if current_edu:
            education.append(current_edu)
        
        return education
    
    def _extract_candidate_name(self, resume_text: str) -> str:
        """Extract candidate name from resume using multiple strategies"""
        try:
            lines = [line.strip() for line in resume_text.split('\n') if line.strip()]
            
            # Strategy 1: Look for name in the first few lines (most common)
            name = self._extract_name_from_top_lines(lines)
            if name:
                return name
            
            # Strategy 2: Look for name using spaCy NER
            name = self._extract_name_with_spacy(resume_text)
            if name:
                return name
            
            # Strategy 3: Look for name patterns in the document
            name = self._extract_name_with_patterns(resume_text)
            if name:
                return name
            
            # Strategy 4: Look for capitalized words that could be names
            name = self._extract_name_from_capitalization(lines)
            if name:
                return name
            
            return "Name Not Found"
            
        except Exception as e:
            logger.error(f"Error extracting candidate name: {e}")
            return "Name Not Found"
    
    def _extract_name_from_top_lines(self, lines: List[str]) -> str:
        """Extract name from the first few lines of the resume"""
        # Check first 5 lines for name patterns
        for i, line in enumerate(lines[:5]):
            # Skip lines that are clearly not names
            if self._is_not_name_line(line):
                continue
            
            # Look for name patterns
            name = self._extract_name_from_line(line)
            if name and self._is_valid_name(name):
                return name
        
        return ""
    
    def _is_not_name_line(self, line: str) -> bool:
        """Check if a line is clearly not a name"""
        line_lower = line.lower()
        
        # Skip lines with common resume headers
        skip_patterns = [
            'resume', 'cv', 'curriculum vitae', 'contact', 'phone', 'email',
            'address', 'objective', 'summary', 'profile', 'experience',
            'education', 'skills', 'certifications', 'projects', 'achievements',
            'references', 'linkedin', 'github', 'portfolio', 'website'
        ]
        
        # Skip lines with email or phone patterns
        if '@' in line or re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', line):
            return True
        
        # Skip lines that are too long (likely not names)
        if len(line) > 50:
            return True
        
        # Skip lines with multiple words that don't look like names
        words = line.split()
        if len(words) > 4:
            return True
        
        # Skip if line contains skip patterns
        return any(pattern in line_lower for pattern in skip_patterns)
    
    def _extract_name_from_line(self, line: str) -> str:
        """Extract potential name from a single line"""
        # Remove common prefixes/suffixes
        line = re.sub(r'^(mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?)\s*', '', line, flags=re.IGNORECASE)
        line = re.sub(r'\s+(jr\.?|sr\.?|iii|ii|iv)$', '', line, flags=re.IGNORECASE)
        
        # Split into words and filter
        words = line.split()
        name_words = []
        
        for word in words:
            # Skip words that are clearly not name parts
            if self._is_name_word(word):
                name_words.append(word)
            else:
                break  # Stop at first non-name word
        
        return ' '.join(name_words) if name_words else ""
    
    def _is_name_word(self, word: str) -> bool:
        """Check if a word could be part of a name"""
        # Must be at least 2 characters
        if len(word) < 2:
            return False
        
        # Must start with capital letter
        if not word[0].isupper():
            return False
        
        # Must contain only letters, hyphens, or apostrophes
        if not re.match(r"^[A-Za-z'-]+$", word):
            return False
        
        # Skip common non-name words
        skip_words = {
            'and', 'or', 'the', 'of', 'in', 'at', 'to', 'for', 'with', 'by',
            'software', 'engineer', 'developer', 'manager', 'analyst', 'consultant',
            'specialist', 'coordinator', 'assistant', 'intern', 'volunteer'
        }
        
        return word.lower() not in skip_words
    
    def _is_valid_name(self, name: str) -> bool:
        """Validate if extracted text is a valid name"""
        if not name or len(name) < 2:
            return False
        
        words = name.split()
        
        # Must have at least first and last name
        if len(words) < 2:
            return False
        
        # Each word must be a valid name word
        for word in words:
            if not self._is_name_word(word):
                return False
        
        # Check for reasonable length
        if len(name) > 50:
            return False
        
        return True
    
    def _extract_name_with_spacy(self, text: str) -> str:
        """Extract name using spaCy NER"""
        if not self.nlp:
            return ""
        
        try:
            doc = self.nlp(text)
            
            # Look for PERSON entities in the first part of the document
            first_half = text[:len(text)//2]
            first_doc = self.nlp(first_half)
            
            for ent in first_doc.ents:
                if ent.label_ == "PERSON":
                    # Clean up the entity
                    name = ent.text.strip()
                    if self._is_valid_name(name):
                        return name
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting name with spaCy: {e}")
            return ""
    
    def _extract_name_with_patterns(self, text: str) -> str:
        """Extract name using regex patterns"""
        try:
            # Pattern 1: First line that looks like a name
            lines = text.split('\n')
            for line in lines[:3]:
                line = line.strip()
                if not line:
                    continue
                
                # Pattern: FirstName LastName (with optional middle name)
                name_pattern = r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)$'
                match = re.match(name_pattern, line)
                if match:
                    name = match.group(1)
                    if self._is_valid_name(name):
                        return name
            
            # Pattern 2: Look for name after common headers
            header_patterns = [
                r'(?i)(?:name|full name|candidate name):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'(?i)(?:applicant|candidate):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
            ]
            
            for pattern in header_patterns:
                match = re.search(pattern, text)
                if match:
                    name = match.group(1).strip()
                    if self._is_valid_name(name):
                        return name
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting name with patterns: {e}")
            return ""
    
    def _extract_name_from_capitalization(self, lines: List[str]) -> str:
        """Extract name based on capitalization patterns"""
        try:
            for line in lines[:5]:
                line = line.strip()
                if not line or self._is_not_name_line(line):
                    continue
                
                # Look for lines with proper name capitalization
                words = line.split()
                if len(words) >= 2 and len(words) <= 4:
                    # Check if all words are properly capitalized
                    if all(word[0].isupper() and word[1:].islower() for word in words if word):
                        name = ' '.join(words)
                        if self._is_valid_name(name):
                            return name
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting name from capitalization: {e}")
            return ""
    
    def get_sentence_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get sentence embeddings for texts"""
        try:
            if self.sentence_transformer:
                embeddings = self.sentence_transformer.encode(texts)
                return embeddings.tolist()

            if self.fallback_vectorizer is not None:
                matrix = self.fallback_vectorizer.transform(texts)
                return matrix.astype(np.float32).toarray().tolist()

            return []
        except Exception as e:
            logger.error(f"Error getting sentence embeddings: {e}")
            return []

    def compare_models(self, pairs: List[Tuple[str, str]], baseline_model_name: str = "all-MiniLM-L6-v2") -> Dict[str, Any]:
        """Compare the configured embedding model against a smaller baseline model."""
        baseline_service = NLPService(sentence_transformer_model=baseline_model_name)

        comparisons: List[Dict[str, Any]] = []
        for left_text, right_text in pairs:
            current_score = self.calculate_semantic_similarity(left_text, right_text)
            baseline_score = baseline_service.calculate_semantic_similarity(left_text, right_text)
            comparisons.append(
                {
                    "left_text": left_text,
                    "right_text": right_text,
                    "current_model": self.sentence_transformer_model,
                    "current_similarity": float(current_score),
                    "baseline_model": baseline_model_name,
                    "baseline_similarity": float(baseline_score),
                    "delta": float(current_score - baseline_score),
                }
            )

        def mean(values: List[float]) -> float:
            return float(sum(values) / len(values)) if values else 0.0

        return {
            "current_model": self.sentence_transformer_model,
            "baseline_model": baseline_model_name,
            "pair_count": len(comparisons),
            "average_current_similarity": mean([item["current_similarity"] for item in comparisons]),
            "average_baseline_similarity": mean([item["baseline_similarity"] for item in comparisons]),
            "average_delta": mean([item["delta"] for item in comparisons]),
            "pairs": comparisons,
        }
    
    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts"""
        try:
            embeddings = self.get_sentence_embeddings([text1, text2])
            if len(embeddings) != 2:
                return 0.0
            similarity = self._cosine_similarity(embeddings[0], embeddings[1])
            return float(similarity)
        except Exception as e:
            logger.error(f"Error calculating semantic similarity: {e}")
            return 0.0
    
    def _cosine_similarity(self, vec1, vec2) -> float:
        """Calculate cosine similarity between two vectors"""
        import numpy as np
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from text using TextBlob"""
        if not TextBlob:
            logger.warning("TextBlob is not installed; keyword extraction disabled.")
            return []
        
        try:
            blob = TextBlob(text)
            # Get noun phrases and individual words
            keywords = []
            
            # Add noun phrases
            for phrase in blob.noun_phrases:
                if len(phrase.split()) <= 3:  # Limit to 3-word phrases
                    keywords.append(phrase)
            
            # Add important words (nouns, adjectives)
            for word, pos in blob.tags:
                if pos in ['NN', 'NNS', 'NNP', 'NNPS', 'JJ', 'JJR', 'JJS']:
                    if len(word) > 3 and word.lower() not in ['the', 'and', 'for', 'with']:
                        keywords.append(word)
            
            # Remove duplicates and return top keywords
            unique_keywords = list(dict.fromkeys(keywords))
            return unique_keywords[:max_keywords]
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
