from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from typing import Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)

class ElasticsearchClient:
    def __init__(self, disabled: bool = False):
        self.client = None
        self.disabled = disabled
        if not self.disabled:
            self.connect()
        else:
            logger.info("Elasticsearch client disabled via DISABLE_EXTERNAL_SERVICES")
    
    def connect(self):
        if self.disabled:
            return
        try:
            auth_kwargs = {}
            if settings.ELASTICSEARCH_API_KEY:
                auth_kwargs["api_key"] = settings.ELASTICSEARCH_API_KEY
            elif settings.ELASTICSEARCH_USERNAME and settings.ELASTICSEARCH_PASSWORD:
                auth_kwargs["basic_auth"] = (
                    settings.ELASTICSEARCH_USERNAME,
                    settings.ELASTICSEARCH_PASSWORD,
                )
            
            # Elasticsearch 8.x client configuration
            self.client = Elasticsearch(
                hosts=[settings.ELASTICSEARCH_URL],
                verify_certs=False,
                ssl_show_warn=False,
                request_timeout=30,
                **auth_kwargs
            )
            
            # Test connection with info() instead of ping() for better error handling
            info = self.client.info()
            logger.info(f"Connected to Elasticsearch {info['version']['number']}")
        except Exception as e:
            logger.error(f"Elasticsearch connection error: {e}")
            self.client = None
    
    def get_client(self):
        if self.disabled:
            return None
        if not self.client:
            self.connect()
        return self.client

class Neo4jClient:
    def __init__(self, disabled: bool = False):
        self.driver = None
        self.disabled = disabled
        if not self.disabled:
            self.connect()
        else:
            logger.info("Neo4j client disabled via DISABLE_EXTERNAL_SERVICES")
    
    def connect(self):
        if self.disabled:
            return
        try:
            username = settings.NEO4J_USER or settings.NEO4J_USERNAME or "neo4j"
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,

                auth=(settings.neo4j_username, settings.NEO4J_PASSWORD)
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"Connected to Neo4j at {settings.NEO4J_URI}")
        except Exception as e:
            logger.error(f"Neo4j connection error: {e}")
    
    def get_session(self):
        if self.disabled or not self.driver:
            raise RuntimeError("Neo4j client is disabled")
        if not self.driver:
            self.connect()
        if not self.driver:
            raise ConnectionError("Neo4j driver is not available. Check connection settings.")
        return self.driver.session()
    
    def close(self):
        if self.driver:
            self.driver.close()

# Global instances
es_client = ElasticsearchClient(
    disabled=settings.DISABLE_EXTERNAL_SERVICES or settings.DISABLE_ELASTICSEARCH
)
neo4j_client = Neo4jClient(disabled=settings.DISABLE_EXTERNAL_SERVICES)

def get_elasticsearch() -> Elasticsearch:
    return es_client.get_client()

def get_neo4j():
    return neo4j_client
