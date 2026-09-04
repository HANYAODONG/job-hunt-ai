from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Job Matching API"
    
    # Database Settings
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ELASTICSEARCH_USERNAME: Optional[str] = None
    ELASTICSEARCH_PASSWORD: Optional[str] = None
    ELASTICSEARCH_API_KEY: Optional[str] = None
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: Optional[str] = "neo4j"  # For backwards compatibility
    NEO4J_USERNAME: Optional[str] = None  # Neo4j Aura uses USERNAME
    NEO4J_PASSWORD: str = "password"
    NEO4J_USERNAME: Optional[str] = None
    NEO4J_DATABASE: str = "neo4j"
    
    @property
    def neo4j_username(self) -> str:
        """Returns NEO4J_USERNAME if set, otherwise falls back to NEO4J_USER"""
        return self.NEO4J_USERNAME or self.NEO4J_USER or "neo4j"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # File Upload
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "uploads"
    
    # NLP Models
    SPACY_MODEL: str = "en_core_web_sm"
    SENTENCE_TRANSFORMER_MODEL: str = "BAAI/bge-m3"
    ENABLE_SPACY_MODEL: bool = True
    ENABLE_SENTENCE_TRANSFORMER: bool = True
    # Optional resume extraction enhancement.  Matching remains local and
    # closed-set; the LLM is used only to structure resume evidence.
    # LLM is the default extraction enhancement when an API key is present;
    # the parser always falls back to the local extractor when unavailable.
    ENABLE_LLM_RESUME_PARSER: bool = True
    # Uploaded resumes use the local v2 role-first matcher by default. Set to
    # `legacy_hybrid` only when the ES/KG runtime has been explicitly started.
    RESUME_MATCHING_PIPELINE: str = "canonical_two_stage"
    LLM_RESUME_PROVIDER: str = "deepseek"
    LLM_RESUME_API_KEY: Optional[str] = None
    LLM_RESUME_BASE_URL: str = "https://api.deepseek.com"
    LLM_RESUME_MODEL: str = "deepseek-chat"
    LLM_RESUME_TIMEOUT: int = 150
    LLM_RESUME_MAX_TEXT_CHARS: int = 12000
    LLM_RESUME_MAX_TOKENS: int = 1200
    SEMANTIC_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    SEMANTIC_EMBEDDING_DEVICE: str = "cpu"
    SEMANTIC_EMBEDDING_BATCH_SIZE: int = 16
    SEMANTIC_EMBEDDING_NORMALIZE: bool = True
    SEMANTIC_EMBEDDING_TRUST_REMOTE_CODE: bool = True
    HF_TOKEN: Optional[str] = None
    TOKENIZERS_PARALLELISM: Optional[str] = None
    
    # Search Settings
    MAX_SEARCH_RESULTS: int = 100
    DEFAULT_PAGE_SIZE: int = 20
    
    # External API Keys
    LINKEDIN_API_KEY: Optional[str] = None
    INDEED_API_KEY: Optional[str] = None
    GLASSDOOR_API_KEY: Optional[str] = None

    # JD update LLM settings
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    GPT_API_KEY: Optional[str] = None
    GPT_MODEL: str = "gpt-4.1-mini"
    GPT_BASE_URL: str = "https://api.openai.com/v1"
    JOB_UPDATE_TEXT2VEC_MODEL: str = "shibing624/text2vec-base-chinese"
    
    # Job Ingestion Settings
    DEFAULT_INGESTION_LIMIT: int = 50
    MAX_INGESTION_LIMIT: int = 200
    INGESTION_RATE_LIMIT: int = 100  # requests per hour

    # Semantic ANN index
    SEMANTIC_INDEX_PATH: Optional[str] = "artifacts/semantic_index/jobs_embeddings.npy"
    SEMANTIC_INDEX_IDS: Optional[str] = "artifacts/semantic_index/jobs_embedding_ids.json"
    DISABLE_EXTERNAL_SERVICES: bool = False
    DISABLE_ELASTICSEARCH: bool = False
    
    class Config:
        env_file = (Path(__file__).resolve().parents[3] / ".env").as_posix()
        env_file_encoding = "utf-8-sig"
        case_sensitive = True

settings = Settings()
