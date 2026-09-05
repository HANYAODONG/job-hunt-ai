"""Focused coverage for core business seams without external infrastructure.

These tests exercise public service behavior while replacing ES, Neo4j and
embedding clients with small in-memory fakes.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.models.candidate import Candidate, Skill
from app.models.fusion import FusionInput, FusionWeights, LayeredWeights
from app.models.job import ExperienceLevel, Job, JobSearchQuery, JobSearchResult, JobType, Location


def make_job(job_id="job-1", title="后端开发工程师", skills=None, company="Acme"):
    return Job(
        id=job_id,
        title=title,
        description="负责服务端开发",
        company_name=company,
        location=Location(city="北京", state="北京", country="中国"),
        job_type=JobType.FULL_TIME,
        experience_level=ExperienceLevel.MID,
        posted_date=datetime(2026, 1, 1),
        required_skills=skills or ["Python", "SQL"],
        job_family="后端开发工程师",
    )


def make_input(job_id="job-1", **overrides):
    data = dict(
        query_id="resume-1",
        job_id=job_id,
        bm25_score=0.7,
        semantic_score=0.8,
        skill_coverage=0.5,
        job_family_match=1.0,
        graph_relatedness=0.4,
        matched_skills=["Python"],
        missing_skills=["SQL"],
        evidence_paths=["resume.skills -> job.required_skills"],
    )
    data.update(overrides)
    return FusionInput(**data)


class TestFusionMergeService:
    def test_normalize_and_merge_api_preserves_metadata(self):
        from app.services.fusion_merge_service import merge_from_bm25_api, normalize_bm25_scores

        empty = normalize_bm25_scores([])
        assert empty == []
        equal = normalize_bm25_scores([{"job_id": "a", "bm25_score": 2.0}])
        assert equal[0]["bm25_score"] == 1.0
        varied = normalize_bm25_scores([
            {"job_id": "a", "bm25_score": 1.0},
            {"job_id": "b", "bm25_score": 3.0},
        ])
        assert [row["bm25_score"] for row in varied] == [0.0, 1.0]

        result = merge_from_bm25_api(
            "resume-1",
            {
                "total": 2,
                "hits": [
                    {"job_id": "a", "score": 1.0, "title": "后端", "salary": {"min": 10, "max": 20, "currency": "K"}},
                    {"job_id": "b", "score": 3.0, "company_name": "Acme", "location_text": "北京"},
                ],
            },
        )
        assert [item.job_id for item in result] == ["a", "b"]
        assert result[0].model_extra["_meta"]["salary"] == "10-20K"
        assert result[1].model_extra["_meta"]["company"] == "Acme"

    def test_merge_artifacts_handles_all_sources_and_jsonl(self, tmp_path):
        from app.services.fusion_merge_service import merge_from_artifacts, read_jsonl

        merged = merge_from_artifacts(
            bm25_candidates=[{"query_id": "q", "candidates": [{"job_id": "j1", "bm25_score": 2, "bm25_rank": 1}]}],
            semantic_candidates=[{"query_id": "q", "candidates": [{"job_id": "j1", "semantic_score": 0.8, "semantic_rank": 1}, {"job_id": "j2", "semantic_score": 0.2}]}],
            kg_features=[{"query_id": "q", "job_id": "j1", "skill_coverage": 0.75, "job_family_match": 1, "graph_relatedness": 0.4, "matched_skills": ["Python"]}],
        )
        assert set(item.job_id for item in merged["q"]) == {"j1", "j2"}
        j1 = next(item for item in merged["q"] if item.job_id == "j1")
        assert j1.semantic_score == 0.8 and j1.skill_coverage == 0.75

        path = tmp_path / "rows.jsonl"
        path.write_text('{"id": 1}\n\n{"id": 2}\n', encoding="utf-8")
        assert read_jsonl(str(path)) == [{"id": 1}, {"id": 2}]


class TestFusionScoringService:
    def test_weights_scores_explanations_and_batch(self):
        import app.services.fusion_scoring_service as scoring

        scoring.reset_weights()
        assert scoring._normalize_within_batch([]) == []
        assert scoring._normalize_within_batch([1]) == [0.5]
        assert scoring._normalize_within_batch([2, 2]) == [1.0, 1.0]
        assert scoring._family_gate(0.9, 0.2) == 1.0
        assert scoring._family_gate(0.2, 0.3) == 0.3

        old = scoring.get_weights()
        assert scoring.update_weights(FusionWeights(bm25=1, semantic=0, skill_coverage=0, job_family=0, graph=0)).bm25 == 1
        assert scoring.compute_final_score(make_input(bm25_score=0.5), scoring.get_weights()) == 0.5
        scoring.update_weights(old)

        layered = LayeredWeights()
        scoring.update_layered_weights(layered)
        one = scoring.fuse_single(make_input(_meta={"title": "后端"}))
        assert one.rank == 0 and one.meta == {"title": "后端"}
        batch = scoring.fuse_batch([
            make_input("j1", bm25_score=1, semantic_score=1, skill_coverage=1),
            make_input("j2", bm25_score=0.2, semantic_score=0.1, job_family_match=0.1),
        ])
        assert [row.rank for row in batch] == [1, 2]
        assert all(0 <= row.final_score <= 1 for row in batch)
        explanation = scoring.generate_explanation(make_input(), 0.9)
        assert explanation.reason
        scoring.reset_weights()


class TestCandidateGeneration:
    def test_merges_lexical_semantic_and_graph_sources(self):
        from app.services.candidate_generation_service import CandidateGenerationService

        service = CandidateGenerationService.__new__(CandidateGenerationService)
        j1 = make_job("j1")
        j2 = make_job("j2", title="数据工程师")
        j3 = make_job("j3", title="图谱工程师")

        class ES:
            def search_jobs(self, query):
                return SimpleNamespace(jobs=[j1, j2], total_count=8)

            def get_jobs_by_ids(self, ids):
                return [job for job in [j1, j2, j3] if job.id in ids]

        class Semantic:
            def is_available(self):
                return True

            def query(self, text, top_k):
                return [("j2", 0.9), ("j3", 0.7)]

        class KG:
            def find_semantic_matches(self, text):
                return SimpleNamespace(nodes=[SimpleNamespace(type=SimpleNamespace(value="Job"), id="j3")])

        service.es_service, service.semantic_service, service.kg_service = ES(), Semantic(), KG()
        result = service.generate_candidates(JobSearchQuery(query="Python"), max_candidates=3)
        assert {job.id for job in result.jobs} == {"j1", "j2", "j3"}
        assert result.lexical_total_hits == 8
        assert "lexical" in result.jobs[1].search_metadata["candidate_sources"]
        assert "semantic" in result.jobs[1].search_metadata["candidate_sources"]

        service.semantic_service = SimpleNamespace(is_available=lambda: False)
        assert service._semantic_candidates("x", 5) == []


class TestFeatureEngineering:
    def test_builds_lexical_semantic_and_graph_features(self):
        from app.services.feature_engineering_service import FeatureEngineeringService

        service = FeatureEngineeringService.__new__(FeatureEngineeringService)

        class NLP:
            def calculate_semantic_similarity(self, query, text):
                return 0.4 if text else 0.0

            def extract_skills_from_text(self, text):
                return ["Python"]

            def extract_entities_from_text(self, text):
                return {"GPE": ["北京"]}

        class KG:
            def count_job_skill_matches(self, job_id, skills, hops):
                return hops

            def shortest_path_to_skill(self, job_id, skill):
                return 2 if skill == "python" else None

            def shortest_path_to_location(self, job_id, location):
                return 1

        service.nlp_service, service.kg_service = NLP(), KG()
        job = make_job()
        features = service.build_feature_vector("Python 北京", job, ["Python", "SQL"], ["北京"])
        assert features["lexical_es_score"] == 0
        assert features["lexical_skill_overlap_ratio"] == 1
        assert features["lexical_filter_location_match"] == 1
        assert features["kg_skill_1hop_count"] == 1
        assert features["kg_skill_shortest_path"] == 2
        assert features["kg_location_shortest_path"] == 1
        service.build_features_for_jobs("Python", [job], ["Python"], ["北京"])
        assert job.feature_vector and job.search_metadata["last_query_text"] == "Python"
        assert service._extract_query_skills("x") == ["Python"]

        service.kg_service.count_job_skill_matches = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down"))
        fallback = service._kg_features("x", job, ["Python"], [])
        assert fallback["kg_skill_1hop_count"] == 0


class TestKeywordAndLearning:
    def test_keyword_extraction_covers_titles_salary_locations(self):
        from app.services.keyword_extraction_service import KeywordExtractionService

        service = KeywordExtractionService.__new__(KeywordExtractionService)
        service.nlp_service = SimpleNamespace(
            nlp=None,
            sentence_transformer=None,
            extract_skills_from_text=lambda text: ["Python"],
        )
        service.job_title_patterns = [r"\bdata scientist\b"]
        service.job_title_keywords = ["scientist"]
        result = service.extract_keywords("Senior data scientist with Python, $80k annual in San Francisco, CA")
        assert "Python" in result["skills"]
        assert result["salary"]["min"] == 80000
        assert "San Francisco" in result["locations"]
        assert service.extract_keywords(" ") == {"job_titles": [], "skills": [], "salary": None, "locations": []}

    def test_learning_plan_normalizes_prioritizes_and_limits(self):
        from app.services.learning_plan_service import build_learning_plan

        plan = build_learning_plan(
            "后端开发工程师",
            ["Python", {"name": "SQL", "priority": "medium"}, {"skill": "RAG", "priority": "bad"}, ""],
            candidate_name="小王",
            target_version="v2",
            match_score=0.7,
            max_stages=2,
            now=datetime(2026, 1, 2, 3, 4),
        )
        assert plan["gap_count"] == 2
        assert plan["stages"][0]["status"] == "进行中"
        assert plan["missing_skills"][0]["priority"] == "high"
        assert plan["updated_at"] == "2026-01-02 03:04"


class TestAuthAndBackup:
    def test_auth_register_login_token_and_invalid_paths(self):
        from fastapi import HTTPException
        from passlib.context import CryptContext
        import app.services.auth_service as auth_module
        from app.services.auth_service import AuthService
        from app.models.user import UserLogin, UserRegistration

        # Keep this unit test independent of the locally installed bcrypt ABI.
        auth_module.pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
        service = AuthService()
        user = service.register_user(UserRegistration(email="a@example.com", password="secret123", first_name="Ann", last_name="Bee"))
        assert service.verify_password("secret123", user.hashed_password)
        assert service.authenticate_user("a@example.com", "wrongpass") is None
        token = service.login_user(UserLogin(email="a@example.com", password="secret123"))
        assert service.get_current_user(token.access_token).email == "a@example.com"
        assert service.verify_token("bad-token") is None
        with pytest.raises(HTTPException):
            service.register_user(UserRegistration(email="a@example.com", password="secret123", first_name="Ann", last_name="Bee"))
        with pytest.raises(HTTPException):
            service.get_current_user("bad-token")

    def test_backup_create_and_list_with_missing_files(self, monkeypatch, tmp_path):
        import app.services.backup_service as backup

        monkeypatch.setattr(backup, "BACKUP_ROOT", tmp_path / "backups")
        monkeypatch.setattr(backup, "BACKUP_FILES", [tmp_path / "present.txt", tmp_path / "missing.txt"])
        (tmp_path / "present.txt").write_text("ok", encoding="utf-8")
        result = backup.create_backup("test")
        assert result["files"][0]["status"] == "copied"
        assert result["files"][1]["status"] == "missing"
        assert backup.list_backups()[0]["reason"] == "test"


class TestGraphAndCandidateBuilders:
    def test_job_and_candidate_jsonl_builders(self, monkeypatch, tmp_path):
        import app.services.kg_builder as jobs_builder
        import app.services.kg_builder_candidates as candidate_builder

        class KG:
            def __init__(self):
                self.created = []

            def create_job_node(self, job):
                self.created.append(job.id)
                return True

            def create_candidate_node(self, candidate):
                self.created.append(candidate.id)
                return True

        fake = KG()
        monkeypatch.setattr(jobs_builder, "kg_service", fake)
        monkeypatch.setattr(candidate_builder, "kg_service", fake)
        assert jobs_builder.create_job_with_skills({"job_id": "j", "title": "后端", "description": "x", "skills": ["Python"]})
        jobs_path = tmp_path / "jobs.jsonl"
        jobs_path.write_text(json.dumps({"id": "j2", "title": "数据", "description": "SQL", "skills": []}, ensure_ascii=False) + "\n", encoding="utf-8")
        loaded = jobs_builder.load_jobs_from_jsonl(jobs_path)
        assert loaded[0]["job_id"] == "j2"
        assert len(jobs_builder.get_sample_jobs()) == 5
        assert candidate_builder.create_candidate_with_skills({"candidate_id": "c", "name": "N", "skills": ["Python"]})
        candidate_path = tmp_path / "candidates.jsonl"
        candidate_path.write_text(json.dumps({"id": "c2", "profile_text": "x", "skills": ["SQL"]}) + "\n", encoding="utf-8")
        assert candidate_builder.load_candidates_from_jsonl(candidate_path)[0]["candidate_id"] == "c2"


class TestGraphEmbeddingAndSemanticANN:
    def test_graph_embedding_fallback_and_similarity(self, monkeypatch):
        import app.services.graph_embedding as graph

        monkeypatch.setattr(graph, "load_model", lambda: (None, None))
        assert graph.get_graph_relatedness("c", "j") == 0.5
        model = SimpleNamespace(wv=SimpleNamespace(get_vector=lambda value: np.array([1.0, 0.0]) if value == "c" else np.array([0.0, 1.0])))
        monkeypatch.setattr(graph, "load_model", lambda: (model, {}))
        assert graph.get_graph_relatedness("c", "j") == 0.5
        model.wv.get_vector = lambda value: (_ for _ in ()).throw(KeyError(value))
        assert graph.get_graph_relatedness("c", "j") == 0.0
        assert graph.train_node2vec_model([]) is None

    def test_semantic_ann_bruteforce_and_text_ranking(self):
        from app.services.semantic_ann_service import SemanticANNService

        service = SemanticANNService.__new__(SemanticANNService)
        service.enabled = True
        service.index = None
        service.job_ids = ["j1", "j2"]
        service.normalized_embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        service.embeddings = service.normalized_embeddings
        service.nlp_service = SimpleNamespace(get_sentence_embeddings=lambda texts: [np.array([1.0, 0.0]) for _ in texts])
        assert service.query("x", 1)[0][0] == "j1"
        ranked = service.rank_candidate_ids("x", ["j2", "j1", "j1"])
        assert [row["job_id"] for row in ranked] == ["j1", "j2"]
        text_ranked = service.rank_candidate_texts("x", {"j1": "a", "j2": "b"})
        assert text_ranked[0]["job_id"] == "j1"
        assert service.rank_candidate_texts("x", {}) == []
        assert service._normalize(np.array([[3.0, 4.0]])).round(3).tolist() == [[0.6, 0.8]]


class TestDataIngestion:
    def test_ingestion_success_empty_and_error_paths(self):
        from app.services.data_ingestion_service import DataIngestionService

        service = DataIngestionService.__new__(DataIngestionService)
        job = make_job()

        class Rise:
            async def fetch_and_map_jobs(self, page, limit, location):
                return [job]

        class NLP:
            def extract_entities_from_text(self, text):
                return []

            def extract_skills_from_text(self, text):
                return ["Docker"]

        class ES:
            def index_job(self, item):
                return True

            async def get_job_count(self):
                return 1

        class KG:
            def create_job_node(self, item): return True
            def create_company_node(self, *args): return True
            def create_location_node(self, *args): return True
            def create_skill_node(self, *args): return True
            def create_job_skill_relationship(self, *args): return True
            def create_job_company_relationship(self, *args): return True
            def create_job_location_relationship(self, *args): return True
            def get_job_count(self): return 1

        service.rise_service, service.nlp_service, service.es_service, service.kg_service = Rise(), NLP(), ES(), KG()
        result = asyncio.run(service.ingest_rise_jobs(index_to_elasticsearch=True, create_neo4j_nodes=True))
        assert result["success"] and result["jobs_processed"] == 1
        assert asyncio.run(service.process_jobs_with_pipeline([job]))["jobs"][0].required_skills
        assert asyncio.run(service.get_ingestion_status())["elasticsearch_jobs"] == 1

        service.rise_service.fetch_and_map_jobs = lambda *args, **kwargs: asyncio.sleep(0, result=[])
        assert asyncio.run(service.ingest_rise_jobs())["success"] is False

        async def broken(*args, **kwargs):
            raise RuntimeError("broken")

        service.rise_service.fetch_and_map_jobs = broken
        assert asyncio.run(service.ingest_rise_jobs())["success"] is False


class TestResumeService:
    def test_resume_parsing_profile_and_insights(self, tmp_path):
        from app.services.resume_service import ResumeService

        service = ResumeService.__new__(ResumeService)
        service.upload_dir = str(tmp_path)
        service.nlp_service = SimpleNamespace(
            nlp=None,
            extract_candidate_profile=lambda text: {
                "name": "张三",
                "contact_info": {"emails": ["z@example.com"], "phones": ["13800000000"], "locations": ["北京"]},
                "skills": ["Python", "FastAPI", "SQL", "沟通"],
                "education": [{"institution": "大学", "degree": "本科"}],
                "experience": [{"company": "Acme", "title": "Senior Engineer", "description": "服务端开发"}],
                "summary": "后端开发",
                "years_experience": 4,
            },
        )
        service.kg_service = SimpleNamespace(create_candidate_node=lambda candidate: True)
        parsed = service.parse_resume_text("张三 z@example.com", mode="enhanced")
        assert parsed["email"] == "z@example.com"
        assert service._extract_emails_simple("a@x.com b@y.org") == ["a@x.com", "b@y.org"]
        candidate = service._create_candidate_from_profile(parsed | {"contact_info": {"emails": ["z@example.com"], "locations": ["北京"]}}, "c1", "resume.txt")
        assert candidate.id == "c1" and candidate.skills[0].name == "Python"
        categories = service._categorize_skills(["Python", "FastAPI", "SQL", "Figma", "沟通"])
        assert categories["programming_languages"] == ["Python"]
        assert categories["frameworks"] == ["FastAPI"]
        assert categories["databases"] == ["SQL"]
        assert "Figma" in categories["tools"] and "沟通" in categories["other"]
        assert service._create_experience_summary([]).startswith("No work")
        profile = service._create_candidate_from_profile(
            {"name": "张三", "skills": ["Python"], "experience": [{"title": "Senior Engineer", "company": "Acme", "description": "做事"}], "education": []},
            "c2", "resume.txt",
        )
        profile_data = service._create_candidate_from_profile({"name": "张三", "skills": ["Python"], "experience": [], "education": []}, "c3", "resume.txt")
        from app.models.candidate import CandidateProfile
        cp = CandidateProfile(candidate=profile, extracted_skills=["Python"], extracted_experience=["Senior Engineer"], skill_categories=categories, experience_summary="Senior Engineer at Acme")
        insights = service.get_resume_insights(cp)
        assert insights["experience_analysis"]["career_progression"]["leadership_roles"]
        assert insights["marketability_score"] > 0
        assert service._analyze_career_progression([])["has_progression"] is False
        assert service._get_improvement_suggestions(CandidateProfile(candidate=profile_data, extracted_skills=[]))[0]
        upload = asyncio.run(service.save_uploaded_file(b"abc", "resume.txt", "c1"))
        assert upload.file_size == 3 and upload.file_type == ".txt"
        assert asyncio.run(service._extract_text_from_file(str(tmp_path / upload.file_name))) == "abc"


class TestRerankingService:
    def test_keyword_and_profile_reranking_helpers(self):
        from app.services.reranking_service import RerankingService
        from app.models.candidate import CandidateProfile

        service = RerankingService.__new__(RerankingService)
        service.weights = {"skill_match": 0.35, "experience_match": 0.25, "location_preference": 0.15, "salary_expectation": 0.10, "semantic_similarity": 0.10, "company_preference": 0.05}
        service.feature_labels = {"lexical_es_score": "ES"}
        service.nlp_service = SimpleNamespace(calculate_semantic_similarity=lambda a, b: 0.8)
        service.ai_scoring_service = SimpleNamespace(is_available=lambda: False)
        job = make_job()
        job.salary = SimpleNamespace(min_salary=100, max_salary=200, period="yearly")
        candidate = Candidate(
            id="c", name="N", email="n@example.com", location="北京", skills=[], experience=[], education=[],
            certifications=[], languages=[], preferred_locations=["北京, 北京"], salary_expectation=150,
            created_at=datetime.now(), updated_at=datetime.now(),
        )
        profile = CandidateProfile(candidate=candidate, extracted_skills=["Python", "Docker"], extracted_experience=["Senior Engineer"])
        keywords = {"job_titles": ["后端开发工程师"], "skills": ["Python"], "locations": ["北京"], "salary": {"min": 120, "max": 180}}
        scores = service._calculate_keyword_match_scores(job, keywords)
        assert scores["job_title"] == 1.0 and scores["skill"] == 1.0 and scores["location"] == 1.0
        result = service.rerank_with_keywords(SimpleNamespace(jobs=[job], total_count=1, page=1, page_size=10, total_pages=1, search_time_ms=1), keywords)
        assert result.jobs[0].rerank_score > 0
        assert service._calculate_skill_match_score(job, profile) > 0
        assert service._calculate_experience_match_score(job, profile) == 0.8
        assert service._calculate_location_preference_score(job, profile) == 1.0
        assert service._calculate_salary_expectation_score(job, profile) == 1.0
        assert service._calculate_semantic_similarity_score(job, "后端") == 0.8
        assert service._companies_similar("Acme Cloud", "Acme Labs") is True
        assert service.update_reranking_weights({"skill_match": 0.5}) is False
        assert service.update_reranking_weights(service.weights.copy()) is True
        explanation = service.get_reranking_explanation(job, "后端", profile)
        assert explanation["scoring_method"] == "Rule-based analysis"
        stats = service.get_reranking_statistics(SimpleNamespace(jobs=[SimpleNamespace(rerank_score=0.9), SimpleNamespace(rerank_score=0.2)]))
        assert stats["total_jobs"] == 2 and stats["high_quality_matches"] == 1


class TestHybridSearchHelpers:
    def test_constraints_scores_and_query_enrichment(self):
        from app.services.hybrid_search_service import HybridSearchService

        service = HybridSearchService.__new__(HybridSearchService)
        service.job_static_cache = {}
        service.nlp_service = SimpleNamespace(
            extract_hard_constraints=lambda text: {
                "must_have_certifications": ["PMP"] if "PMP" in text else [],
                "min_degree": "master" if "硕士" in text else None,
                "min_years_experience": 3 if "三年" in text else None,
                "language_requirements": ["English"] if "English" in text else [],
                "security_clearance": "Secret" if "Secret" in text else None,
                "licensure_requirements": ["PE"] if "PE" in text else [],
                "requires_us_work_auth": False,
                "no_visa_sponsorship": False,
            },
            extract_entities_from_text=lambda text: {"GPE": ["北京"]},
            extract_skills_from_text=lambda text: ["Python"],
            get_sentence_embeddings=lambda texts: [[0.1, 0.2]],
            extract_keywords=lambda text: {"skills": ["Python"]},
            calculate_semantic_similarity=lambda a, b: 0.8,
        )
        service.kg_service = SimpleNamespace(
            find_related_skills=lambda skills: ["FastAPI"],
            count_job_skill_matches=lambda *args, **kwargs: 2,
        )
        candidate = Candidate(
            id="c", name="N", email="n@example.com", location="北京", skills=[Skill(name="Python", level="advanced", category="technical", years_experience=4)],
            certifications=[], languages=[], visa_status="", created_at=datetime.now(), updated_at=datetime.now(), years_experience=4,
        )
        jobs = [make_job("j1"), make_job("j2", title="项目经理")]
        jobs[1].description = "需要 PMP 硕士 三年 English Secret PE"
        filtered, reasons, prompts = service._filter_jobs_by_hard_constraints(jobs, candidate)
        assert len(filtered) == 1 and "certification" in reasons["j2"]
        enriched = service._enrich_query("Python 北京")
        assert "FastAPI" in enriched["all_skills"]
        service._ensure_job_static_features(jobs[0])
        assert jobs[0].search_metadata["static_features"]["skill_count"] == 2
        assert service._calculate_direct_skill_match(jobs[0], candidate)["matching_skills"] == 1
        assert service._calculate_direct_skill_match(make_job("empty", skills=[]), candidate)["skill_match_ratio"] == 0.5
        assert service._calculate_location_match(jobs[0], candidate) == 1.0
        jobs[0].salary = SimpleNamespace(min_salary=100, max_salary=200)
        candidate.salary_expectation = 150
        assert service._calculate_salary_match(jobs[0], candidate) == 1.0
        candidate.visa_status = "H1B"
        assert service._calculate_visa_match(jobs[0], candidate) == 0.0
        score, explanation = service._calculate_overall_score({"skill_match_ratio": 0.8, "matched_skill_names": ["Python"]}, 0.8, 1.0, 1.0, 1.0, candidate, jobs[0])
        assert score > 0.5 and explanation["top_features"]


class TestAnalyticsService:
    @staticmethod
    def _tables():
        import pandas as pd
        from app.services.data_source_service import SourceTables

        frequency = pd.DataFrame([
            {"standard_job": "后端开发工程师", "month": "2026-01", "skill": "Python", "monthly_skill_frequency": "0.8", "monthly_skill_count": "8", "cumulative_skill_count": 8},
            {"standard_job": "后端开发工程师", "month": "2026-01", "skill": "SQL", "monthly_skill_frequency": 0.4, "monthly_skill_count": 4, "cumulative_skill_count": 4},
            {"standard_job": "后端开发工程师", "month": "2026-02", "skill": "Python", "monthly_skill_frequency": 0.9, "monthly_skill_count": 9, "cumulative_skill_count": 9},
            {"standard_job": "后端开发工程师", "month": "2026-02", "skill": "Docker", "monthly_skill_frequency": 0.6, "monthly_skill_count": 6, "cumulative_skill_count": 6},
            {"standard_job": "数据工程师", "month": "2026-02", "skill": "SQL", "monthly_skill_frequency": 0.7, "monthly_skill_count": 7, "cumulative_skill_count": 7},
        ])
        lifecycle = pd.DataFrame([
            {"standard_job": "后端开发工程师", "skill": "Python", "lifecycle_status": "活跃技能", "current_monthly_skill_frequency": "0.9", "recent_3m_skill_count": 9, "mom_frequency_change": 0.1},
            {"standard_job": "后端开发工程师", "skill": "Docker", "lifecycle_status": "新兴技能", "current_monthly_skill_frequency": 0.6, "recent_3m_skill_count": 6, "mom_frequency_change": 0.6},
        ])
        migration = pd.DataFrame([
            {"skill": "Python", "spread_job_count": "3", "total_skill_mentions": 20},
            {"skill": "SQL", "spread_job_count": 2, "total_skill_mentions": 15},
        ])
        spread = pd.DataFrame([
            {"skill": "Python", "month": "2026-01", "standard_job": "后端开发工程师", "monthly_skill_frequency": 0.8, "monthly_frequency_change": 0.1},
            {"skill": "Python", "month": "2026-02", "standard_job": "数据工程师", "monthly_skill_frequency": 0.7, "monthly_frequency_change": -0.1},
        ])
        snapshots = pd.DataFrame([
            {"standard_job": "后端开发工程师", "month": "2026-01", "skill": "Python", "kg_display_skill": "Python", "monthly_jd_count": 10, "monthly_skill_count": 8, "monthly_skill_frequency": 0.8, "cumulative_jd_count": 10, "cumulative_skill_count": 8, "cumulative_skill_frequency": 0.8, "rank_in_month": 1, "is_core_skill": 1},
            {"standard_job": "后端开发工程师", "month": "2026-01", "skill": "SQL", "kg_display_skill": "SQL", "monthly_jd_count": 10, "monthly_skill_count": 4, "monthly_skill_frequency": 0.4, "cumulative_jd_count": 10, "cumulative_skill_count": 4, "cumulative_skill_frequency": 0.4, "rank_in_month": 2, "is_core_skill": 0},
            {"standard_job": "后端开发工程师", "month": "2026-02", "skill": "Python", "kg_display_skill": "Python", "monthly_jd_count": 12, "monthly_skill_count": 9, "monthly_skill_frequency": 0.9, "cumulative_jd_count": 22, "cumulative_skill_count": 9, "cumulative_skill_frequency": 0.9, "rank_in_month": 1, "is_core_skill": 1},
            {"standard_job": "后端开发工程师", "month": "2026-02", "skill": "Docker", "kg_display_skill": "Docker", "monthly_jd_count": 12, "monthly_skill_count": 6, "monthly_skill_frequency": 0.6, "cumulative_jd_count": 22, "cumulative_skill_count": 6, "cumulative_skill_frequency": 0.6, "rank_in_month": 2, "is_core_skill": 0},
        ])
        diff = pd.DataFrame([
            {"standard_job": "后端开发工程师", "from_month": "2026-01", "to_month": "2026-02", "skill": "Python", "change_type": "频率上升技能", "from_monthly_jd_count": 10, "to_monthly_jd_count": 12, "from_monthly_skill_count": 8, "to_monthly_skill_count": 9, "from_monthly_skill_frequency": 0.8, "to_monthly_skill_frequency": 0.9, "frequency_delta": 0.1, "frequency_delta_ratio": 0.125, "from_cumulative_skill_count": 8, "to_cumulative_skill_count": 9, "from_cumulative_skill_frequency": 0.8, "to_cumulative_skill_frequency": 0.9, "is_stable_core": 0},
            {"standard_job": "后端开发工程师", "from_month": "2026-01", "to_month": "2026-02", "skill": "SQL", "change_type": "消失技能", "from_monthly_jd_count": 10, "to_monthly_jd_count": 12, "from_monthly_skill_count": 4, "to_monthly_skill_count": 0, "from_monthly_skill_frequency": 0.4, "to_monthly_skill_frequency": 0, "frequency_delta": -0.4, "frequency_delta_ratio": -1, "from_cumulative_skill_count": 4, "to_cumulative_skill_count": 4, "from_cumulative_skill_frequency": 0.4, "to_cumulative_skill_frequency": 0, "is_stable_core": 0},
        ])
        current = pd.DataFrame([
            {"standard_job": "后端开发工程师", "skill": "Python", "kg_display_skill": "Python", "monthly_jd_count": 12, "monthly_skill_count": 9, "monthly_skill_frequency": 0.9, "cumulative_jd_count": 22, "cumulative_skill_count": 9, "cumulative_skill_frequency": 0.9, "rank_in_month": 1, "is_core_skill": 1, "source_month": "2026-02", "source_type": "base"},
            {"standard_job": "后端开发工程师", "skill": "Docker", "kg_display_skill": "Docker", "monthly_jd_count": 12, "monthly_skill_count": 6, "monthly_skill_frequency": 0.6, "cumulative_jd_count": 22, "cumulative_skill_count": 6, "cumulative_skill_frequency": 0.6, "rank_in_month": 2, "is_core_skill": 0, "source_month": "2026-02", "source_type": "base"},
        ])
        source = {"key": "base", "label": "测试", "kind": "base", "domain": "company"}
        return SourceTables(source, frequency, lifecycle, migration, spread, snapshots, diff, current)

    def test_public_analytics_views_and_fallbacks(self, monkeypatch):
        import app.services.analytics_service as analytics

        monkeypatch.setattr(analytics, "_tables", lambda *args, **kwargs: self._tables())
        assert analytics.list_jobs() == ["后端开发工程师", "数据工程师"]
        assert analytics.list_months() == ["2026-01", "2026-02"]
        overview = analytics.overview()
        assert overview["latest_month"] == "2026-02" and overview["job_count"] == 2
        trend = analytics.job_trend("后端开发工程师", top_n=1, month_start="2026-01", month_end="2026-02")
        assert trend["standard_job"] == "后端开发工程师" and trend["series"][0]["points"][-1]["count"] == 9
        assert analytics.job_trend("不存在")["series"] == []
        life = analytics.lifecycle(status="新兴技能", limit=1)
        assert life["summary"][0]["status"] == "新兴技能" and len(life["rows"]) == 1
        mig = analytics.migration(skill="Python", limit=1)
        assert mig["selected"]["skill"] == "Python" and len(mig["spread"]) == 2
        rank = analytics.monthly_rank(rank_type="emerging", limit=5)
        assert rank["rows"][0]["skill"] == "Python"
        declining = analytics.monthly_rank(rank_type="declining")
        assert declining["rows"][0]["skill"] == "SQL"
        compare = analytics.profile_compare("后端", from_month="2026-02", to_month="2026-01")
        assert compare["from_month"] == "2026-01" and compare["summary"]["modified"] >= 1
        empty = analytics.profile_compare("没有这个岗位")
        assert empty["from_profile"] == []
        opt = analytics.optimization_profile("后端", limit=1)
        assert opt["skills"][0]["skill"] == "Python" and opt["summary"]["job_count"] == 1

    def test_analytics_helpers_and_source_checks(self):
        import app.services.analytics_service as analytics
        import pandas as pd

        assert analytics._clamp("bad", 1, 3) == 1
        assert analytics._round_float("bad") == 0.0
        assert analytics._clean_value(pd.NA) == ""
        assert analytics._resolve_job(pd.DataFrame({"standard_job": ["后端开发工程师"]}), "后端") == "后端开发工程师"
        assert analytics._filter_month_range(pd.DataFrame({"month": ["2026-01", "2026-02"]}), "month", "2026-02", None).shape[0] == 1
        assert analytics._empty_profile_compare("x", "a", "b")["summary"]["added"] == 0


class TestHybridSearchBusinessPaths:
    def _candidate(self):
        return Candidate(
            id="c1", name="候选人", email="c@example.com", location="北京",
            summary="后端开发", skills=[Skill(name="Python", level="advanced", years_experience=4, category="technical")],
            experience=[], education=[], certifications=[], languages=[], visa_status="",
            created_at=datetime.now(), updated_at=datetime.now(), years_experience=4,
        )

    def test_search_pipeline_without_candidate_and_exception_fallback(self):
        from app.services.hybrid_search_service import HybridSearchService
        from app.models.knowledge_graph import GraphNode, GraphSearchResult, NodeType

        service = HybridSearchService.__new__(HybridSearchService)
        job = make_job("j1")
        graph_result = GraphSearchResult(nodes=[GraphNode(id="j1", type=NodeType.JOB, properties={})], relationships=[])
        service.nlp_service = SimpleNamespace(
            extract_hard_constraints=lambda text: {},
            extract_entities_from_text=lambda text: {"GPE": ["北京"]},
            extract_skills_from_text=lambda text: ["Python"],
            get_sentence_embeddings=lambda texts: [[0.1, 0.2]],
            extract_keywords=lambda text: {"skills": ["Python"]},
            calculate_semantic_similarity=lambda a, b: 0.8,
        )
        service.kg_service = SimpleNamespace(
            find_semantic_matches=lambda text: graph_result,
            find_related_skills=lambda skills: [],
            count_job_skill_matches=lambda *args, **kwargs: 1,
        )
        service.feature_service = SimpleNamespace(build_features_for_jobs=lambda **kwargs: None)
        service.candidate_service = SimpleNamespace(
            generate_candidates=lambda *args, **kwargs: SimpleNamespace(
                jobs=[job], lexical_total_hits=1, source_breakdown={"lexical": 1}
            )
        )
        service.job_static_cache = {}
        result = service.search_jobs_with_semantic_matching(JobSearchQuery(query="Python", page_size=5))
        assert result.total_count == 1 and result.jobs[0].rerank_score == pytest.approx(1.2)
        service.candidate_service.generate_candidates = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down"))
        fallback = service.search_jobs_with_semantic_matching(JobSearchQuery(query="Python"))
        assert fallback.jobs == [] and fallback.total_count == 0

    def test_profile_analysis_decomposition_market_and_recommendation_fallbacks(self):
        from app.services.hybrid_search_service import HybridSearchService
        from app.models.knowledge_graph import GraphSearchResult
        from app.models.candidate import CandidateProfile

        service = HybridSearchService.__new__(HybridSearchService)
        service.kg_service = SimpleNamespace(
            find_related_skills=lambda skills: ["FastAPI"],
            get_skill_relationships=lambda skill: ["uses", "related"],
        )
        service.es_service = SimpleNamespace()
        service.reranking_service = SimpleNamespace()
        candidate = self._candidate()
        query = service._decompose_resume_to_query(candidate)
        assert query["experience_level"] == "mid" and "Python" in query["required_skills"]
        job = make_job("j2", skills=["Python", "FastAPI"])
        job.experience_level = ExperienceLevel.MID
        analysis = service._analyze_job_candidate_match(job, candidate)
        assert analysis["matching_skills"] == ["python"] and analysis["overall_fit"] in {"good", "fair"}
        assert service._determine_overall_fit(1, 1, 1, 1) == "excellent"
        assert service._determine_overall_fit(0, 0, 0, 0) == "poor"
        trends = service.analyze_job_market_trends(["Python"])
        assert trends["skill_demand"]["Python"] == 2
        service.search_jobs_with_semantic_matching = lambda *args, **kwargs: JobSearchResult(jobs=[], total_count=0, page=1, page_size=10, total_pages=0, search_time_ms=0)
        assert service.get_job_recommendations(candidate, limit=2) == []
        assert service.get_personalized_recommendations(
            CandidateProfile(candidate=candidate, extracted_skills=["Python"]), limit=2
        ).jobs == []


class TestJobServicePurePaths:
    def test_payload_normalization_and_serialization_helpers(self):
        import pandas as pd
        import app.services.job_service as jobs

        frame = pd.DataFrame([
            {"month": "2026-02", "title": "后端开发工程师", "responsibility": "开发", "requirement": "Python"},
            {"month": "2026-02", "title": "数据工程师", "responsibility": "分析", "requirement": "SQL"},
        ])
        normalized = jobs._normalize_import_frame(frame)
        assert list(normalized["job_title"]) == ["后端开发工程师", "数据工程师"]
        with pytest.raises(ValueError):
            jobs._normalize_import_frame(pd.DataFrame({"foo": ["x"]}))
        posting = jobs._posting_from_payload({"month": "2026-02", "job_title": "后端开发工程师", "responsibility": "开发", "requirement": "Python"}, source="test")
        assert posting.month == "2026-02" and posting.job_id
        assert jobs._input_payload({"source": "csv"}, posting)["source"] == "csv"
        assert jobs._category_for_job("后端开发工程师", {"top_jobs": [{"name": "后端开发工程师", "metadata": {"category": "研发"}}]}) == "研发"
        assert jobs._generate_job_id("2026-02", "后端开发工程师").startswith("web_202602_")

    def test_monthly_import_defaults_to_manual_review_mode(self, monkeypatch):
        import pandas as pd
        import app.services.job_service as jobs

        seen = []
        monkeypatch.setattr(jobs, "_build_system", lambda *args, **kwargs: object())
        monkeypatch.setattr(jobs, "_ensure_database_initialized", lambda: None)
        monkeypatch.setattr(jobs.SQLiteJobUpdateStore, "migrate", lambda self: None)
        monkeypatch.setattr(jobs, "submit_one_dry_run", lambda payload, **kwargs: seen.append(payload) or {"status": "pending"})
        result = jobs.import_csv(pd.DataFrame([{"job_title": "新岗位", "month": "2026-08"}]))
        assert result["count"] == 1
        assert seen[0]["processing_mode"] == "manual"

    def test_preview_and_submit_paths_use_public_update_contract(self, monkeypatch):
        import app.services.job_service as jobs

        class FakeSystem:
            def __init__(self, result):
                self.result = result

            def process(self, *args, **kwargs):
                return self.result

        route = SimpleNamespace(
            status="existing_job",
            best_job=SimpleNamespace(name="后端开发工程师"),
            best_category=SimpleNamespace(name="研发"),
        )
        result = SimpleNamespace(route=route, update=SimpleNamespace(normalized_skills=[]), admissions=[])
        monkeypatch.setattr(jobs, "_ensure_database_initialized", lambda: None)
        monkeypatch.setattr(jobs, "_build_system", lambda progress: FakeSystem(result))
        monkeypatch.setattr(jobs, "serialize_review_process_result", lambda result, **kwargs: {"route": {"status": "existing_job"}})
        preview = jobs.preview_one({"job_title": "后端开发工程师", "month": "2026-02", "processing_mode": "auto"})
        assert preview["status"] == "preview" and preview["preview_id"]
        monkeypatch.setattr(jobs, "submit_one_dry_run", lambda payload: {"status": "ok", "mode": payload["processing_mode"]})
        assert jobs.submit_preview(preview["preview_id"], "manual")["mode"] == "manual"
        with pytest.raises(KeyError):
            jobs.submit_preview("missing")
        with pytest.raises(ValueError):
            jobs.preview_one({"job_title": "后端开发工程师", "processing_mode": "bad"})

    def test_submit_auto_merge_and_review_queue(self, monkeypatch):
        import app.services.job_service as jobs

        with pytest.raises(ValueError):
            jobs.submit_one_dry_run({"job_title": "后端开发工程师", "processing_mode": "bad"})

        class FakeStore:
            def __init__(self, path):
                self.items = []

            def create_review_item(self, **kwargs):
                item = {"item_id": "review-1", "result": kwargs.get("result_payload", {}), **kwargs}
                self.items.append(item)
                return item

            def update_review_item(self, item_id, **kwargs):
                return {"item_id": item_id, **kwargs}

        route = SimpleNamespace(status="existing_job", best_job=SimpleNamespace(name="后端开发工程师"), best_category=SimpleNamespace(name="研发"))
        result = SimpleNamespace(route=route, update=SimpleNamespace(normalized_skills=[]), normalized_skills=[], admissions=[])
        monkeypatch.setattr(jobs, "_ensure_database_initialized", lambda: None)
        monkeypatch.setattr(jobs, "SQLiteJobUpdateStore", FakeStore)
        monkeypatch.setattr(jobs, "_ensure_database_initialized", lambda: None)
        monkeypatch.setattr(jobs, "_build_system", lambda progress: SimpleNamespace(process=lambda *args, **kwargs: result))
        monkeypatch.setattr(
            jobs,
            "create_pending_reviews",
            lambda **kwargs: ({"skill_reviews": [], "job_review": {"item_id": "job-review", "result": {}}}
                              if kwargs.get("always_queue_job") else {"skill_reviews": []}),
        )
        monkeypatch.setattr(jobs, "capture_current_job_profile", lambda *args: [])
        monkeypatch.setattr(jobs, "_record_live_effect", lambda **kwargs: {"effect_id": "e1"})
        monkeypatch.setattr(jobs, "serialize_review_process_result", lambda *args, **kwargs: {"route": {}})
        monkeypatch.setattr(jobs, "_merge_summary", lambda result: {"event_rows": "updated"})
        merged = jobs.submit_one_dry_run({"job_title": "后端开发工程师", "month": "2026-02", "processing_mode": "auto"})
        assert merged["status"] == "auto_merged" and merged["needs_review"] is False

        route.status = "new_job"
        queued = jobs.submit_one_dry_run({"job_title": "新岗位", "month": "2026-02", "processing_mode": "manual"})
        assert queued["needs_review"] is True

    def test_review_and_maintenance_actions(self, monkeypatch):
        import app.services.job_service as jobs

        class FakeStore:
            items = {
                "job-1": {"item_id": "job-1", "review_type": "job", "submission_mode": "manual", "job_id": "j1", "input": {}, "result": {"skills": []}},
                "skill-1": {"item_id": "skill-1", "review_type": "skill", "submission_mode": "manual", "job_id": "j1", "input": {}, "result": {"skill": {"skill": "Docker"}}},
            }

            def __init__(self, path):
                pass

            def get_review_item(self, item_id):
                return self.items[item_id]

            def create_review_item(self, **kwargs):
                return {"item_id": "maintenance-1", **kwargs}

            def update_review_item(self, item_id, **kwargs):
                return {"item_id": item_id, **kwargs}

            def list_review_items(self, **kwargs):
                return [{"item_id": "job-1"}]

        monkeypatch.setattr(jobs, "SQLiteJobUpdateStore", FakeStore)
        monkeypatch.setattr(jobs, "_ensure_database_initialized", lambda: None)
        proposal = jobs.confirm_new_job(
            "job-1", standard_category="研发", standard_job_title="AI语料工程师",
            match_keywords="语料 SFT", merge_database=False, skills=[]
        )
        assert proposal["status"] == "submitted_dictionary_maintenance"
        mapped = jobs.review_skill(
            "skill-1", decision="mapped", normalized_skill="Docker", kg_display_skill="Docker", skill_type="tool"
        )
        assert mapped["status"] == "reviewed_skill"
        new_skill = jobs.review_skill(
            "skill-1", decision="new_skill", normalized_skill="", kg_display_skill="", skill_type=""
        )
        assert new_skill["status"] == "reviewed_skill"
        assert jobs.get_review_items() == [{"item_id": "job-1"}]
        assert jobs.reject_update("job-1")["status"] == "rejected"
        with pytest.raises(ValueError):
            jobs.confirm_new_job("job-1", standard_category="", standard_job_title="", match_keywords="", merge_database=False)
        with pytest.raises(ValueError):
            jobs.review_skill("job-1", decision="mapped", normalized_skill="x", kg_display_skill="x", skill_type="")


class TestProfileOverridesAndLiveEffects:
    def test_save_and_apply_manual_and_dynamic_profile_changes(self, monkeypatch, tmp_path):
        import app.services.profile_override_service as overrides
        import pandas as pd

        db_path = tmp_path / "profile.sqlite"
        monkeypatch.setattr(overrides, "BASE_DATABASE", db_path)
        base = pd.DataFrame([
            {"standard_job": "后端开发工程师", "skill": "Python", "kg_display_skill": "Python", "is_core_skill": 1},
        ])
        saved = overrides.save_profile_overrides(
            domain="company", standard_job="后端开发工程师",
            changes=[
                {"action": "update", "skill": "Python", "after": {"kg_display_skill": "Python 3", "is_core_skill": True}, "note": "版本标注"},
                {"action": "add", "skill": "Docker", "after": {"kg_display_skill": "Docker"}},
            ],
        )
        assert saved["saved_changes"] == 2
        changed, override_count, candidate_count = overrides.apply_profile_overrides(base, domain="company")
        assert override_count == 2 and candidate_count == 0
        assert set(changed["skill"]) == {"Python", "Docker"}
        assert changed.loc[changed["skill"] == "Python", "manual_status"].iloc[0] == "人工修改"

        overrides.save_profile_overrides(
            domain="company", standard_job="后端开发工程师",
            changes=[{"action": "delete", "skill": "Python", "before": {"skill": "Python"}}],
        )
        deleted, _, _ = overrides.apply_profile_overrides(base, domain="company")
        assert "Python" not in set(deleted["skill"])
        with pytest.raises(ValueError):
            overrides.save_profile_overrides(domain="company", standard_job="", changes=[])
        with pytest.raises(ValueError):
            overrides.save_profile_overrides(domain="company", standard_job="x", changes=[{"action": "add", "skill": "Go"}])

    def test_live_effect_diff_and_persistence(self, monkeypatch, tmp_path):
        import app.services.live_update_effect_service as effects

        db_path = tmp_path / "effects.sqlite"
        monkeypatch.setattr(effects, "BASE_DATABASE", db_path)
        before = [
            {"skill": "Python", "monthly_skill_frequency": 0.5, "is_core_skill": 1},
            {"skill": "SQL", "monthly_skill_frequency": 0.8, "is_core_skill": 0},
        ]
        after = [
            {"skill": "Python", "monthly_skill_frequency": 0.7, "is_core_skill": 1},
            {"skill": "Docker", "monthly_skill_frequency": 0.3, "is_core_skill": 0},
        ]
        effect = effects.build_live_update_effect(
            standard_job="后端开发工程师", standard_category="研发", month="2026-02",
            before_profile=before, after_profile=after, submitted_skills=["Python", "Python", "Docker", ""],
        )
        assert effect["summary"]["increased"] == 1
        assert effect["summary"]["removed"] == 1
        assert effect["summary"]["signal_skills"] == 2
        saved = effects.record_live_update_effect("company", job_id="j1", effect=effect)
        loaded = effects.get_live_update_effect("company", saved["effect_id"])
        assert loaded["job_id"] if "job_id" in loaded else True
        assert loaded["standard_job"] == "后端开发工程师"
        with pytest.raises(KeyError):
            effects.get_live_update_effect("company", "missing")
        assert effects._truthy("YES") and not effects._truthy("no") and effects._number({"x": "bad"}, "x") == 0


class TestSemanticEmbeddingService:
    def test_fallback_encode_similarity_rerank_and_persistence(self, monkeypatch, tmp_path):
        import app.services.semantic_embedding_service as embedding

        monkeypatch.setattr(embedding, "SentenceTransformer", None)
        service = embedding.SemanticEmbeddingService(model_name="test-model", batch_size=2)
        assert service.model_status == "fallback"
        assert service.encode_texts([]) == []
        vectors = service.encode_texts(["Python SQL", "Python SQL"])
        assert len(vectors) == 2 and len(vectors[0]) == 64
        assert service.encode_text("") == []
        assert service.compute_similarity("", "x") == 0.0
        assert service.compute_similarity("Python", "Python") == pytest.approx(1.0)
        ranked = service.rerank_candidates("Python", ["SQL", "Python"], ["a", "b"])
        assert ranked[0]["job_id"] == "b" and ranked[0]["semantic_rank"] == 1
        assert service.rerank_candidates("", ["x"]) == []
        compared = service.compare_models([("Python", "Python")])
        assert compared["model_family"] == "bge-m3" and compared["results"][0]["similarity"] > 0.9
        path = tmp_path / "vectors.npy"
        ids = tmp_path / "ids.json"
        service.save_embeddings(np.asarray(vectors), path)
        service.save_embedding_ids(["a", "b"], ids)
        assert path.exists() and json.loads(ids.read_text(encoding="utf-8")) == ["a", "b"]
        assert service._cosine_similarity(np.zeros(2), np.ones(2)) == 0.0


class TestText2VecEmbeddingService:
    def test_text2vec_fallback_and_io(self, monkeypatch, tmp_path):
        import app.services.text2vec_embedding_service as text2vec

        monkeypatch.setattr(text2vec, "SentenceTransformer", None)
        service = text2vec.Text2VecEmbeddingService(model_name="test-text2vec", batch_size=4)
        assert service.model_status == "fallback" and service.model_size_mb == 0.0
        assert service.encode_texts([]) == []
        vectors = service.encode_texts(["Python 后端", "Python 后端"])
        assert len(vectors) == 2 and len(vectors[0]) == 64
        assert len(service.encode_text("")) == 64
        assert service.compute_similarity("", "x") == 0.0
        assert service.compute_similarity("Python", "Python") == pytest.approx(1.0)
        ranked = service.rerank_candidates("Python", ["SQL", "Python"], ["a", "b"])
        assert ranked[0]["job_id"] == "b"
        assert service.rerank_candidates("", ["x"]) == []
        assert service._cosine_similarity(np.zeros(2), np.ones(2)) == 0.0
        path = tmp_path / "text2vec.npy"
        ids = tmp_path / "text2vec_ids.json"
        service.save_embeddings(np.asarray(vectors), path)
        service.save_embedding_ids(["a", "b"], ids)
        assert service.load_embeddings(path).shape == (2, 64)
        assert service.load_embedding_ids(ids) == ["a", "b"]
        with pytest.raises(FileNotFoundError):
            service.load_embeddings(tmp_path / "missing.npy")
        with pytest.raises(FileNotFoundError):
            service.load_embedding_ids(tmp_path / "missing.json")
        info = service.get_model_info()
        assert info["model_family"] == "text2vec" and info["model_status"] == "fallback"


class TestRoleTaxonomyCoverage:
    def test_real_world_refinement_and_matching_boundaries(self):
        from app.services.role_taxonomy import (
            get_canonical_taxonomy, get_role_direction, get_standard_role_taxonomy,
            infer_government_tech_role, refine_standard_role, role_affinity, role_match_grade,
        )

        cases = [
            ("AI应用", "AI应用工程师", "AI产品经理", "AI产品经理"),
            ("AI应用", "AI应用工程师", "前端开发", "AI应用前端工程师"),
            ("AI应用", "AI应用工程师", "全栈开发", "AI应用全栈工程师"),
            ("AI应用", "AI应用工程师", "后端服务", "AI应用后端工程师"),
            ("AI应用", "AI应用工程师", "Agent智能体", "Agent应用工程师"),
            ("软件研发", "软件开发工程师", "大数据开发", "大数据开发工程师"),
            ("软件研发", "软件开发工程师", "服务器开发", "服务器开发工程师"),
            ("AI基础设施", "AI Infra工程师", "训练系统", "大模型训练系统工程师"),
            ("AI基础设施", "AI Infra工程师", "推理优化", "大模型推理优化工程师"),
            ("算法", "算法工程师", "推荐算法", "推荐算法工程师"),
            ("算法", "算法工程师", "NLP算法", "算法工程师"),
            ("基础设施", "云计算工程师", "SRE", "SRE工程师"),
            ("基础设施", "云计算工程师", "云原生", "云原生工程师"),
            ("硬件", "硬件工程师", "电子工程师", "电子工程师"),
            ("测试质量", "测试工程师", "性能测试", "性能测试工程师"),
            ("测试质量", "测试工程师", "模型评测", "模型评测工程师"),
            ("安全", "安全工程师", "数据安全", "数据安全工程师"),
            ("安全", "安全工程师", "渗透测试", "渗透测试工程师"),
            ("产品", "AI产品经理", "数据产品", "数据产品经理"),
            ("产品", "AI产品经理", "产品运营", "产品运营经理"),
            ("技术支持", "技术支持工程师", "现场交付", "技术交付工程师"),
            ("技术支持", "解决方案工程师", "售前方案", "售前技术工程师"),
            ("数据", "数据分析师", "数据科学家", "数据科学家"),
            ("数据", "数据分析师", "BI分析报表", "BI分析师"),
        ]
        for category, role, title, expected in cases:
            assert refine_standard_role(category, role, title=title) == expected
        assert refine_standard_role("数据", "数据分析师", skills=["因果推断", "实验设计", "机器学习"]) == "数据科学家"
        assert refine_standard_role("其他", "普通岗位", title="普通") == "普通岗位"
        assert role_match_grade("后端开发工程师", "Java后端开发") == 3
        assert role_match_grade("后端开发工程师", "数据工程师") >= 1
        assert role_affinity("陌生岗位", "陌生岗位") == 1.0
        assert get_role_direction("软件研发", "后端开发工程师") == "服务端与通用开发"
        assert get_standard_role_taxonomy("后端开发工程师")
        assert get_standard_role_taxonomy("不存在") is None
        assert get_canonical_taxonomy("算法", "推荐算法工程师")[0] == "算法与智能"
        assert infer_government_tech_role(["computer_software"])[2] == "政务软件信息化技术岗"
        assert infer_government_tech_role([])[2] == "政务信息化技术岗"


class TestEndpointContracts:
    def test_bm25_search_candidate_and_error_contracts(self, monkeypatch):
        from fastapi import HTTPException
        import app.api.endpoints.bm25 as bm25

        class Service:
            def search(self, **kwargs):
                return {"index_name": "jobs-v2", "took_ms": 4, "total": 2, "hits": [{"job_id": "j1", "score": 0.9, "rank": 1}]}

            def stats(self):
                return {"documents": 2}

        monkeypatch.setattr(bm25, "get_service", lambda: Service())
        request = bm25.BM25SearchRequest(query="Python")
        assert bm25.search_jobs(request)["total"] == 2
        candidates = bm25.retrieve_candidates(bm25.BM25CandidateRequest(query="Python", query_id="resume-1"))
        assert candidates["query_id"] == "resume-1" and candidates["candidates"][0]["bm25_score"] == 0.9
        assert bm25.index_stats()["documents"] == 2

        monkeypatch.setattr(bm25, "get_service", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        with pytest.raises(HTTPException) as exc:
            bm25.search_jobs(request)
        assert exc.value.status_code == 500

    def test_graph_cache_and_role_job_endpoint(self, monkeypatch):
        import asyncio
        import app.api.endpoints.graph as graph

        monkeypatch.setattr(graph.talent_data_service, "list_standard_role_records", lambda: [{"category": "研发", "direction": "后端", "role": "后端开发工程师", "skills": ["Python"]}])
        graph.invalidate_capability_graph_cache()
        first = asyncio.run(graph.get_capability_graph())
        second = asyncio.run(graph.get_capability_graph())
        assert first == second and first["source"] == "canonical_standard_role_taxonomy"
        monkeypatch.setattr(graph.talent_data_service, "list_standard_role_jobs", lambda *args: [{"job_id": "j1"}])
        assert asyncio.run(graph.get_standard_role_jobs("研发", "后端", "后端开发工程师", limit=999, offset=-1)) == [{"job_id": "j1"}]

    def test_graph_year_over_year_growth_uses_previous_snapshot(self):
        from app.api.endpoints.graph import build_standard_role_graph

        def record(year, role="后端开发工程师"):
            return {
                "publish_time": f"{year}-06-01",
                "standard_category": "软件工程",
                "standard_direction": "服务端与通用开发",
                "standard_role": role,
                "is_mapped_canonical_role": True,
                "skills": ["Python"],
            }

        records = [
            record(2024), record(2024),
            record(2025), record(2025), record(2025),
            record(2025, "全栈开发工程师"),
        ]
        baseline = build_standard_role_graph(records, year=2024)
        current = build_standard_role_graph(records, year=2025)
        domain = current["tree"]["children"][0]
        roles = domain["children"][0]["children"]

        assert baseline["tree"]["growth"] == "基准年"
        assert current["tree"]["growth"] == "+100.0%"
        assert domain["growth"] == "+100.0%"
        assert next(node for node in roles if node["label"] == "后端开发工程师")["growth"] == "+50.0%"
        assert next(node for node in roles if node["label"] == "全栈开发工程师")["growth"] == "新增"
