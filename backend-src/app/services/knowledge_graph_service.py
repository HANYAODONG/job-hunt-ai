from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional, Tuple
import logging
from ..core.database import get_neo4j
from ..models.knowledge_graph import (
    GraphNode, GraphRelationship, KnowledgeGraphQuery, 
    GraphSearchResult, NodeType, RelationshipType
)
from ..models.job import Job
from ..models.candidate import Candidate
from ..models.user import User, UserApplication

logger = logging.getLogger(__name__)

class KnowledgeGraphService:
    def __init__(self):
        self.neo4j = get_neo4j()
        # Initialize disabled attribute based on Neo4j client state
        self.disabled = self.neo4j is None or (hasattr(self.neo4j, 'disabled') and self.neo4j.disabled)
        # Setup constraints lazily - don't block initialization
        try:
            self.setup_constraints()
        except Exception as e:
            logger.warning(f"Could not setup constraints during initialization: {e}. Will retry on first use.")
    
    def _is_neo4j_available(self):
        """Check if Neo4j is available"""
        return self.neo4j and self.neo4j.driver is not None
    
    def setup_constraints(self):
        """Set up database constraints and indexes"""
        if not self._is_neo4j_available():
            logger.warning("Neo4j not available, skipping constraint setup")
            return
            
        constraints = [
            "CREATE CONSTRAINT job_id_unique IF NOT EXISTS FOR (j:Job) REQUIRE j.id IS UNIQUE",
            "CREATE CONSTRAINT candidate_id_unique IF NOT EXISTS FOR (c:Candidate) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT user_email_unique IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE",
            "CREATE CONSTRAINT skill_name_unique IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT company_name_unique IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT location_unique IF NOT EXISTS FOR (l:Location) REQUIRE (l.city, l.state, l.country) IS UNIQUE"
        ]
        
        try:
            with self.neo4j.get_session() as session:
                for constraint in constraints:
                    try:
                        session.run(constraint)
                    except Exception as e:
                        logger.warning(f"Constraint setup warning: {e}")
        except Exception as e:
            logger.warning(f"Failed to setup constraints: {e}")
    
    def create_job_node(self, job: Job) -> bool:
        """Create a job node in the knowledge graph"""
        if not self._is_neo4j_available():
            logger.warning("Neo4j not available, skipping job node creation")
            return False
        try:
            with self.neo4j.get_session() as session:
                # Create job node
                job_query = """
                MERGE (j:Job {id: $job_id})
                SET j.title = $title,
                    j.description = $description,
                    j.job_type = $job_type,
                    j.experience_level = $experience_level,
                    j.remote_allowed = $remote_allowed,
                    j.visa_sponsorship = $visa_sponsorship,
                    j.posted_date = $posted_date,
                    j.job_family = $job_family,
                    j.source = $source
                """
                
                session.run(job_query, {
                    "job_id": job.id,
                    "title": job.title,
                    "description": job.description,
                    "job_type": job.job_type,
                    "experience_level": job.experience_level,
                    "remote_allowed": job.remote_allowed,
                    "visa_sponsorship": job.visa_sponsorship,
                    "posted_date": job.posted_date.isoformat(),
                    "job_family": getattr(job, 'job_family', None),
                    "source": getattr(job, 'source', None)
                })
                
                # Create company node and relationship
                company_query = """
                MERGE (c:Company {name: $company_name})
                MERGE (j:Job {id: $job_id})
                MERGE (j)-[:OFFERED_BY]->(c)
                """
                session.run(company_query, {
                    "company_name": job.company_name,
                    "job_id": job.id
                })
                
                # Create location node and relationship
                location_query = """
                MERGE (l:Location {city: $city, state: $state, country: $country})
                MERGE (j:Job {id: $job_id})
                MERGE (j)-[:LOCATED_IN]->(l)
                """
                session.run(location_query, {
                    "city": job.location.city,
                    "state": job.location.state,
                    "country": job.location.country,
                    "job_id": job.id
                })
                
                # Create skill nodes and relationships
                for skill in job.required_skills:
                    skill_query = """
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (j:Job {id: $job_id})
                    MERGE (j)-[:REQUIRES_SKILL {required: true}]->(s)
                    """
                    session.run(skill_query, {
                        "skill_name": skill,
                        "job_id": job.id
                    })
                
                for skill in job.preferred_skills:
                    skill_query = """
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (j:Job {id: $job_id})
                    MERGE (j)-[:REQUIRES_SKILL {required: false}]->(s)
                    """
                    session.run(skill_query, {
                        "skill_name": skill,
                        "job_id": job.id
                    })
                
                # Create benefit nodes and relationships
                for benefit in job.benefits:
                    benefit_query = """
                    MERGE (b:Benefit {name: $benefit_name, category: $category})
                    MERGE (j:Job {id: $job_id})
                    MERGE (j)-[:OFFERS_BENEFIT]->(b)
                    """
                    session.run(benefit_query, {
                        "benefit_name": benefit.name,
                        "category": benefit.category,
                        "job_id": job.id
                    })
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating job node: {e}")
            return False
    
    def create_candidate_node(self, candidate: Candidate) -> bool:
        """Create a candidate node in the knowledge graph"""
        if self.disabled:
            return False
        try:
            with self.neo4j.get_session() as session:
                # Create candidate node
                candidate_query = """
                MERGE (c:Candidate {id: $candidate_id})
                SET c.name = $name,
                    c.email = $email,
                    c.location = $location,
                    c.summary = $summary,
                    c.visa_status = $visa_status,
                    c.salary_expectation = $salary_expectation,
                    c.target_job_family = $target_job_family,
                    c.years_experience = $years_experience
                """
                
                session.run(candidate_query, {
                    "candidate_id": candidate.id,
                    "name": candidate.name,
                    "email": candidate.email,
                    "location": candidate.location,
                    "summary": candidate.summary,
                    "visa_status": candidate.visa_status,
                    "salary_expectation": candidate.salary_expectation,
                    "target_job_family": getattr(candidate, 'target_job_family', None),
                    "years_experience": getattr(candidate, 'years_experience', None)
                })
                
                # Create skill relationships
                for skill in candidate.skills:
                    skill_query = """
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (c:Candidate {id: $candidate_id})
                    MERGE (c)-[:HAS_SKILL {level: $level, years_experience: $years_experience}]->(s)
                    """
                    session.run(skill_query, {
                        "skill_name": skill.name,
                        "candidate_id": candidate.id,
                        "level": skill.level or "intermediate",
                        "years_experience": skill.years_experience or 0
                    })
                
                # Create experience relationships
                for exp in candidate.experience:
                    # Build relationship properties dynamically to avoid null values
                    rel_props = {
                        "position": exp.position,
                        "start_date": exp.start_date.isoformat()
                    }
                    
                    # Only add end_date if it's not null
                    if exp.end_date:
                        rel_props["end_date"] = exp.end_date.isoformat()
                    
                    # Build the query dynamically
                    props_str = ", ".join([f"{k}: ${k}" for k in rel_props.keys()])
                    company_query = f"""
                    MERGE (comp:Company {{name: $company_name}})
                    MERGE (c:Candidate {{id: $candidate_id}})
                    MERGE (c)-[:WORKED_AT {{{props_str}}}]->(comp)
                    """
                    
                    # Add candidate_id and company_name to the parameters
                    query_params = {
                        "company_name": exp.company,
                        "candidate_id": candidate.id,
                        **rel_props
                    }
                    
                    session.run(company_query, query_params)
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating candidate node: {e}")
            return False
    
    def create_company_node(self, company_name: str, company_data: Dict[str, Any] = None) -> bool:
        """Create a company node in the knowledge graph"""
        if self.disabled:
            return False
        try:
            with self.neo4j.get_session() as session:
                query = """
                MERGE (c:Company {name: $company_name})
                SET c.industry = $industry,
                    c.size = $size,
                    c.website = $website,
                    c.description = $description
                """
                
                session.run(query, {
                    "company_name": company_name,
                    "industry": company_data.get("industry") if company_data else None,
                    "size": company_data.get("size") if company_data else None,
                    "website": company_data.get("website") if company_data else None,
                    "description": company_data.get("description") if company_data else None
                })
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating company node: {e}")
            return False
    
    def create_location_node(self, location) -> bool:
        """Create a location node in the knowledge graph"""
        if self.disabled:
            return False
        try:
            with self.neo4j.get_session() as session:
                query = """
                MERGE (l:Location {city: $city, state: $state, country: $country})
                SET l.latitude = $latitude, l.longitude = $longitude
                """
                
                # Extract coordinates safely
                latitude = None
                longitude = None
                if location.coordinates:
                    if isinstance(location.coordinates, dict):
                        latitude = location.coordinates.get('latitude')
                        longitude = location.coordinates.get('longitude')
                    elif isinstance(location.coordinates, list) and len(location.coordinates) == 2:
                        latitude = location.coordinates[0]
                        longitude = location.coordinates[1]
                
                session.run(query, {
                    "city": location.city,
                    "state": location.state,
                    "country": location.country,
                    "latitude": latitude,
                    "longitude": longitude
                })
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating location node: {e}")
            return False
    
    def create_skill_node(self, skill_name: str) -> bool:
        """Create a skill node in the knowledge graph"""
        if self.disabled:
            return False
        try:
            with self.neo4j.get_session() as session:
                query = """
                MERGE (s:Skill {name: $skill_name})
                """
                
                session.run(query, {"skill_name": skill_name})
                return True
                
        except Exception as e:
            logger.error(f"Error creating skill node: {e}")
            return False
    
    def create_job_company_relationship(self, job_id: str, company_name: str) -> bool:
        """Create a relationship between job and company"""
        if self.disabled:
            return False
        try:
            with self.neo4j.get_session() as session:
                query = """
                MATCH (j:Job {id: $job_id})
                MATCH (c:Company {name: $company_name})
                MERGE (j)-[:WORKED_AT]->(c)
                """
                
                session.run(query, {
                    "job_id": job_id,
                    "company_name": company_name
                })
                return True
                
        except Exception as e:
            logger.error(f"Error creating job-company relationship: {e}")
            return False
    
    def create_job_location_relationship(self, job_id: str, location_id: str) -> bool:
        """Create a relationship between job and location"""
        if self.disabled:
            return False
        try:
            with self.neo4j.get_session() as session:
                query = """
                MATCH (j:Job {id: $job_id})
                MATCH (l:Location)
                WHERE l.city + '_' + l.state + '_' + l.country = $location_id
                MERGE (j)-[:LOCATED_IN]->(l)
                """
                
                session.run(query, {
                    "job_id": job_id,
                    "location_id": location_id
                })
                return True
                
        except Exception as e:
            logger.error(f"Error creating job-location relationship: {e}")
            return False
    
    def create_job_skill_relationship(self, job_id: str, skill_name: str) -> bool:
        """Create a relationship between job and skill"""
        if self.disabled:
            return False
        try:
            with self.neo4j.get_session() as session:
                query = """
                MATCH (j:Job {id: $job_id})
                MATCH (s:Skill {name: $skill_name})
                MERGE (j)-[:REQUIRES_SKILL]->(s)
                """
                
                session.run(query, {
                    "job_id": job_id,
                    "skill_name": skill_name
                })
                return True
                
        except Exception as e:
            logger.error(f"Error creating job-skill relationship: {e}")
            return False

    def count_job_skill_matches(self, job_id: str, skills: List[str], hops: int = 1) -> int:
        """Count how many query skills connect to the job within given hops."""
        if self.disabled or not skills:
            return 0
        normalized = [skill.lower() for skill in skills if skill]
        if not normalized:
            return 0
        try:
            with self.neo4j.get_session() as session:
                if hops == 1:
                    query = """
                    MATCH (j:Job {id: $job_id})-[:REQUIRES_SKILL]->(s:Skill)
                    WHERE toLower(s.name) IN $skills
                    RETURN count(DISTINCT s) AS count
                    """
                else:
                    query = """
                    MATCH (qs:Skill)
                    WHERE toLower(qs.name) IN $skills
                    MATCH (qs)-[:RELATED_TO*1..2]-(s:Skill)<-[:REQUIRES_SKILL]-(j:Job {id: $job_id})
                    RETURN count(DISTINCT s) AS count
                    """
                result = session.run(query, {"job_id": job_id, "skills": normalized})
                record = result.single()
                return int(record["count"]) if record and record["count"] is not None else 0
        except Exception as e:
            logger.error(f"Error counting skill matches for job {job_id}: {e}")
            return 0

    def shortest_path_to_skill(self, job_id: str, skill_name: str) -> Optional[int]:
        """Return shortest path length from query skill to job node."""
        if self.disabled or not skill_name:
            return None
        try:
            with self.neo4j.get_session() as session:
                query = """
                MATCH (s:Skill)
                WHERE toLower(s.name) = $skill
                WITH s LIMIT 1
                MATCH (j:Job {id: $job_id})
                MATCH p = shortestPath((s)-[r*..4]-(j))
                WHERE ALL(rel IN r WHERE type(rel) IN ['RELATED_TO', 'REQUIRES_SKILL'])
                RETURN length(p) AS length
                """
                record = session.run(query, {
                    "skill": skill_name.lower(),
                    "job_id": job_id
                }).single()
                if record and record["length"] is not None:
                    return int(record["length"])
        except Exception as e:
            logger.error(f"Error computing skill path for job {job_id}: {e}")
        return None

    def shortest_path_to_location(self, job_id: str, location_token: str) -> Optional[int]:
        """Return shortest path length from job to a location token."""
        if self.disabled or not location_token:
            return None
        try:
            with self.neo4j.get_session() as session:
                query = """
                MATCH (j:Job {id: $job_id})
                MATCH (l:Location)
                WHERE toLower(l.city) = $token OR toLower(l.state) = $token OR toLower(l.country) = $token
                MATCH p = shortestPath((j)-[r*..4]-(l))
                WHERE ALL(rel IN r WHERE type(rel) IN ['LOCATED_IN', 'RELATED_TO'])
                RETURN length(p) AS length
                ORDER BY length
                LIMIT 1
                """
                record = session.run(query, {
                    "job_id": job_id,
                    "token": location_token.lower()
                }).single()
                if record and record["length"] is not None:
                    return int(record["length"])
        except Exception as e:
            logger.error(f"Error computing location path for job {job_id}: {e}")
        return None
    def find_related_skills(self, skills: List[str], max_depth: int = 2) -> List[str]:
        """Find skills related to the given skills through the knowledge graph"""
        try:
            with self.neo4j.get_session() as session:
                # Use a fixed depth since Neo4j doesn't support parameterized relationship depth
                if max_depth == 1:
                    query = """
                    MATCH (s:Skill)
                    WHERE s.name IN $skills
                    MATCH (s)-[:RELATED_TO]-(related:Skill)
                    RETURN DISTINCT related.name as skill_name
                    """
                else:
                    query = """
                    MATCH (s:Skill)
                    WHERE s.name IN $skills
                    MATCH (s)-[:RELATED_TO*1..2]-(related:Skill)
                    RETURN DISTINCT related.name as skill_name
                    """
                
                result = session.run(query, {
                    "skills": skills
                })
                
                return [record["skill_name"] for record in result]
                
        except Exception as e:
            logger.error(f"Error finding related skills: {e}")
            return []
    
    def find_semantic_matches(self, query_text: str, entity_types: List[str] = None) -> GraphSearchResult:
        """Find semantic matches for a query using graph traversal"""
        try:
            with self.neo4j.get_session() as session:
                # This is a simplified version - in practice, you'd use more sophisticated NLP
                # to extract entities and then traverse the graph
                
                # Extract potential entities from query (simplified)
                query_lower = query_text.lower()
                potential_skills = []
                potential_locations = []
                potential_companies = []
                
                # Find matching skills
                skill_query = """
                MATCH (s:Skill)
                WHERE toLower(s.name) CONTAINS $query_part
                RETURN s.name as skill_name
                LIMIT 10
                """
                
                for word in query_lower.split():
                    if len(word) > 3:  # Skip short words
                        result = session.run(skill_query, {"query_part": word})
                        potential_skills.extend([record["skill_name"] for record in result])
                
                # Find jobs that match the criteria
                job_query = """
                MATCH (j:Job)-[:REQUIRES_SKILL]->(s:Skill)
                WHERE s.name IN $skills
                OPTIONAL MATCH (j)-[:OFFERED_BY]->(c:Company)
                OPTIONAL MATCH (j)-[:LOCATED_IN]->(l:Location)
                OPTIONAL MATCH (j)-[:OFFERS_BENEFIT]->(b:Benefit)
                RETURN j, c, l, collect(DISTINCT s.name) as job_skills, collect(DISTINCT b.name) as benefits
                ORDER BY size(job_skills) DESC
                LIMIT 50
                """
                
                result = session.run(job_query, {"skills": potential_skills})
                
                nodes = []
                relationships = []
                
                for record in result:
                    job = record["j"]
                    company = record["c"]
                    location = record["l"]
                    
                    nodes.append(GraphNode(
                        id=job["id"],
                        type=NodeType.JOB,
                        properties=dict(job)
                    ))
                    
                    if company:
                        nodes.append(GraphNode(
                            id=company["name"],
                            type=NodeType.COMPANY,
                            properties=dict(company)
                        ))
                    
                    if location:
                        nodes.append(GraphNode(
                            id=f"{location['city']}_{location['state']}",
                            type=NodeType.LOCATION,
                            properties=dict(location)
                        ))
                
                return GraphSearchResult(
                    nodes=nodes,
                    relationships=relationships,
                    relevance_scores={}
                )
                
        except Exception as e:
            logger.error(f"Error finding semantic matches: {e}")
            return GraphSearchResult(nodes=[], relationships=[])
    
    def calculate_job_candidate_match(self, job_id: str, candidate_id: str) -> Dict[str, Any]:
        """Calculate match score between a job and candidate"""
        try:
            with self.neo4j.get_session() as session:
                query = """
                MATCH (j:Job {id: $job_id})-[:REQUIRES_SKILL]->(js:Skill)
                MATCH (c:Candidate {id: $candidate_id})-[:HAS_SKILL]->(cs:Skill)
                
                WITH j, c, 
                     collect(DISTINCT js.name) as job_skills,
                     collect(DISTINCT cs.name) as candidate_skills,
                     collect(DISTINCT js.name) + collect(DISTINCT cs.name) as all_skills
                
                WITH j, c, job_skills, candidate_skills, all_skills,
                     size(job_skills) as total_job_skills,
                     size(candidate_skills) as total_candidate_skills,
                     size([skill IN job_skills WHERE skill IN candidate_skills]) as matching_skills
                
                RETURN j.id as job_id,
                       c.id as candidate_id,
                       total_job_skills,
                       total_candidate_skills,
                       matching_skills,
                       toFloat(matching_skills) / toFloat(total_job_skills) as skill_match_ratio,
                       job_skills,
                       candidate_skills
                """
                
                result = session.run(query, {
                    "job_id": job_id,
                    "candidate_id": candidate_id
                })
                
                record = result.single()
                if record:
                    return {
                        "job_id": record["job_id"],
                        "candidate_id": record["candidate_id"],
                        "total_job_skills": record["total_job_skills"],
                        "total_candidate_skills": record["total_candidate_skills"],
                        "matching_skills": record["matching_skills"],
                        "skill_match_ratio": record["skill_match_ratio"],
                        "job_skills": record["job_skills"],
                        "candidate_skills": record["candidate_skills"]
                    }
                
                return {}
                
        except Exception as e:
            logger.error(f"Error calculating job-candidate match: {e}")
            return {}
    
    def get_skill_relationships(self, skill_name: str) -> List[Dict[str, Any]]:
        """Get relationships for a specific skill"""
        try:
            with self.neo4j.get_session() as session:
                query = """
                MATCH (s:Skill {name: $skill_name})-[r]-(related)
                RETURN type(r) as relationship_type, 
                       labels(related)[0] as related_type,
                       related.name as related_name,
                       r
                """
                
                result = session.run(query, {"skill_name": skill_name})
                
                relationships = []
                for record in result:
                    relationships.append({
                        "type": record["relationship_type"],
                        "related_type": record["related_type"],
                        "related_name": record["related_name"],
                        "properties": dict(record["r"])
                    })
                
                return relationships
                
        except Exception as e:
            logger.error(f"Error getting skill relationships: {e}")
            return []
    
    def create_skill_relationships(self, relationships: List[Dict[str, Any]]) -> bool:
        """Create relationships between skills"""
        try:
            with self.neo4j.get_session() as session:
                for rel in relationships:
                    query = """
                    MERGE (s1:Skill {name: $skill1})
                    MERGE (s2:Skill {name: $skill2})
                    MERGE (s1)-[r:RELATED_TO]->(s2)
                    SET r.relationship_type = $rel_type,
                        r.confidence = $confidence
                    """
                    
                    session.run(query, {
                        "skill1": rel["skill1"],
                        "skill2": rel["skill2"],
                        "rel_type": rel.get("type", "related"),
                        "confidence": rel.get("confidence", 0.5)
                    })
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating skill relationships: {e}")
            return False
    
    def create_user_node(self, user: User) -> bool:
        """Create a user node in the knowledge graph"""
        try:
            with self.neo4j.get_session() as session:
                # Create user node
                user_query = """
                MERGE (u:User {id: $user_id})
                SET u.first_name = $first_name,
                    u.last_name = $last_name,
                    u.email = $email,
                    u.hashed_password = $hashed_password,
                    u.role = $role,
                    u.is_active = $is_active,
                    u.created_at = $created_at,
                    u.updated_at = $updated_at,
                    u.last_login = $last_login
                """
                
                session.run(user_query, {
                    "user_id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "hashed_password": user.hashed_password,
                    "role": user.role.value,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat(),
                    "updated_at": user.updated_at.isoformat(),
                    "last_login": user.last_login.isoformat() if user.last_login else None
                })
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating user node: {e}")
            return False
    
    def create_application_relationship(self, user_id: str, job_id: str, application_data: dict) -> bool:
        """Create a relationship between user and job when they apply"""
        try:
            with self.neo4j.get_session() as session:
                # Create application relationship
                application_query = """
                MATCH (u:User {id: $user_id})
                MATCH (j:Job {id: $job_id})
                MERGE (u)-[r:HAS_APPLIED]->(j)
                SET r.applied_at = $applied_at,
                    r.application_data = $application_data,
                    r.status = $status
                """
                
                session.run(application_query, {
                    "user_id": user_id,
                    "job_id": job_id,
                    "applied_at": datetime.utcnow().isoformat(),
                    "application_data": application_data,
                    "status": "submitted"
                })
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating application relationship: {e}")
            return False
    
    def get_user_applications(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all applications for a user"""
        try:
            with self.neo4j.get_session() as session:
                query = """
                MATCH (u:User {id: $user_id})-[r:HAS_APPLIED]->(j:Job)
                RETURN j.id as job_id,
                       j.title as job_title,
                       j.company_name as company_name,
                       r.applied_at as applied_at,
                       r.status as status,
                       r.application_data as application_data
                ORDER BY r.applied_at DESC
                """
                
                result = session.run(query, {"user_id": user_id})
                
                applications = []
                for record in result:
                    applications.append({
                        "job_id": record["job_id"],
                        "job_title": record["job_title"],
                        "company_name": record["company_name"],
                        "applied_at": record["applied_at"],
                        "status": record["status"],
                        "application_data": record["application_data"]
                    })
                
                return applications
                
        except Exception as e:
            logger.error(f"Error getting user applications: {e}")
            return []
    
    def update_user_skills(self, user_id: str, skills: List[str]) -> bool:
        """Update user's skills in the knowledge graph"""
        try:
            with self.neo4j.get_session() as session:
                # First, remove existing skill relationships
                remove_query = """
                MATCH (u:User {id: $user_id})-[r:HAS_SKILL]->(s:Skill)
                DELETE r
                """
                session.run(remove_query, {"user_id": user_id})
                
                # Add new skill relationships
                for skill in skills:
                    skill_query = """
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (u:User {id: $user_id})
                    MERGE (u)-[:HAS_SKILL {extracted_from: 'resume', confidence: 0.8}]->(s)
                    """
                    session.run(skill_query, {
                        "skill_name": skill,
                        "user_id": user_id
                    })
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating user skills: {e}")
            return False
    
    def update_user_experience(self, user_id: str, experience: List[str]) -> bool:
        """Update user's experience in the knowledge graph"""
        try:
            with self.neo4j.get_session() as session:
                # First, remove existing experience relationships
                remove_query = """
                MATCH (u:User {id: $user_id})-[r:HAS_EXPERIENCE]->(e:Experience)
                DELETE r, e
                """
                session.run(remove_query, {"user_id": user_id})
                
                # Add new experience relationships
                for exp in experience:
                    exp_query = """
                    CREATE (e:Experience {description: $experience_desc})
                    MERGE (u:User {id: $user_id})
                    MERGE (u)-[:HAS_EXPERIENCE {extracted_from: 'resume', confidence: 0.8}]->(e)
                    """
                    session.run(exp_query, {
                        "experience_desc": exp,
                        "user_id": user_id
                    })
                
                return True
                
        except Exception as e:
            logger.error(f"Error updating user experience: {e}")
            return False