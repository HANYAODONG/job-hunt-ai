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
    
    # Job Ingestion Settings
    DEFAULT_INGESTION_LIMIT: int = 50
    MAX_INGESTION_LIMIT: int = 200
    INGESTION_RATE_LIMIT: int = 100  # requests per hour

    # Semantic ANN index
    SEMANTIC_INDEX_PATH: Optional[str] = "artifacts/semantic_index/jobs_embeddings.npy"
    SEMANTIC_INDEX_IDS: Optional[str] = "artifacts/semantic_index/jobs_embedding_ids.json"
    DISABLE_EXTERNAL_SERVICES: bool = False
    
    class Config:
        env_file = (Path(__file__).resolve().parents[3] / ".env").as_posix()
        case_sensitive = True

settings = Settings()
