import json
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.talent_data_service import TalentDataService


class TalentDataServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.jobs_path = root / "jobs.jsonl"
        self.profiles_path = root / "candidate_profiles.jsonl"
        self.state_path = root / "runtime" / "talent_state.json"
        jobs = [
            {
                "job_id": "JOB001",
                "title": "Python 后端工程师",
                "description": "负责服务开发，要求 3 年以上经验",
                "required_skills": ["Python", "Redis"],
                "job_family": "后端开发工程师",
                "standard_category": "软件研发",
                "source_type": "enterprise",
                "source": "enterprise_test",
                "publish_time": "2026-08-01",
            },
            {
                "job_id": "GOV001",
                "title": "信息技术岗",
                "required_skills": ["网络安全"],
                "job_family": "网络安全工程师",
                "standard_category": "网络安全",
                "source_type": "government",
                "source": "government_test",
                "publish_time": "2025-01-01",
            },
        ]
        profiles = [
            {
                "candidate_id": "resume_001_exp03_0",
                "summary": "三年 Python 后端开发经验",
                "target_job_family": "后端开发工程师",
                "standard_category": "软件研发",
                "skills_normalized": ["Python", "Redis"],
                "years_experience": 3,
                "education": {"education": "本科", "major": "计算机科学"},
            },
            {
                "candidate_id": "resume_002_exp01_0",
                "summary": "网络安全方向",
                "target_job_family": "网络安全工程师",
                "standard_category": "网络安全",
                "skills_normalized": ["网络安全"],
                "years_experience": 1,
                "education": {"education": "本科", "major": "网络空间安全"},
            },
        ]
        self.jobs_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in jobs),
            encoding="utf-8",
        )
        self.profiles_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in profiles),
            encoding="utf-8",
        )
        self.service = TalentDataService(
            self.jobs_path,
            self.profiles_path,
            self.state_path,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lists_enterprise_jobs_and_reports_all_source_stats(self):
        result = self.service.list_jobs()
        stats = self.service.market_stats()

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["id"], "JOB001")
        self.assertEqual(stats["total_jobs"], 2)
        self.assertEqual(stats["source_type_counts"], {"enterprise": 1, "government": 1})

    def test_candidate_retrieval_is_ranked_and_explainable(self):
        result = self.service.match_candidates("JOB001", limit=2)

        self.assertIsNotNone(result)
        self.assertEqual(result["items"][0]["id"], "resume_001_exp03_0")
        self.assertGreater(result["items"][0]["score"], 80)
        self.assertEqual(result["items"][0]["gaps"], [])
        self.assertEqual(result["total_candidates"], 2)
        self.assertEqual(result["method"], "explainable_candidate_retrieval_v2")
        self.assertTrue(result["items"][0]["isEligible"])
        self.assertEqual(result["retrieval_stats"]["eligible_count"], 1)

    def test_threshold_filters_candidates_and_keeps_pagination_contract(self):
        result = self.service.match_candidates(
            "JOB001",
            min_score=95,
            page=1,
            page_size=10,
        )

        self.assertEqual(result["items"], [])
        self.assertEqual(result["retrieval_stats"]["eligible_count"], 0)
        self.assertEqual(result["retrieval_stats"]["filtered_out_count"], 1)
        self.assertGreater(result["retrieval_stats"]["recommended_threshold"], 55.0)
        self.assertEqual(result["retrieval_stats"]["recommended_pool_count"], 1)

    def test_candidate_explanation_has_grounded_fallback_without_llm(self):
        result = self.service.explain_candidate(
            "JOB001",
            "resume_001_exp03_0",
            use_llm=False,
            min_score=55,
        )

        self.assertEqual(result["mode"], "evidence_rag_fallback")
        self.assertEqual(result["conclusion"], "高度匹配")
        self.assertTrue(result["matched_evidence"])
        self.assertIn("job_excerpt", result["grounded_context"])

    def test_job_edits_and_candidate_stage_are_persisted(self):
        saved = self.service.save_job(
            "JOB001",
            {"requiredSkills": [{"name": "Python", "level": 90}, {"name": "FastAPI", "level": 80}]},
        )
        self.service.update_candidate_stage("JOB001", "resume_001_exp03_0", "入围")
        reloaded = TalentDataService(self.jobs_path, self.profiles_path, self.state_path)
        candidates = reloaded.match_candidates("JOB001", limit=1, min_score=0)

        self.assertEqual([item["name"] for item in saved["requiredSkills"]], ["Python", "FastAPI"])
        self.assertEqual(candidates["items"][0]["status"], "入围")

    def test_standard_role_jobs_use_saved_jd_overrides(self):
        graph_service = TalentDataService(self.jobs_path, self.profiles_path, self.state_path)
        # Prime the independent graph-side state cache before the edit.
        graph_service.list_standard_role_jobs("软件研发", "服务端与通用开发", "后端开发工程师", limit=10)
        self.service.save_job(
            "JOB001",
            {
                "summary": "更新后的岗位说明",
                "requiredSkills": [{"name": "Python", "level": 95}, {"name": "FastAPI", "level": 85}],
            },
        )

        result = self.service.list_standard_role_jobs(
            "软件研发", "服务端与通用开发", "后端开发工程师", limit=10,
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["summary"], "更新后的岗位说明")
        self.assertEqual([item["name"] for item in result["items"][0]["requiredSkills"]], ["Python", "FastAPI"])

        graph_service.invalidate_runtime_state_cache()
        refreshed = graph_service.list_standard_role_records()
        role_record = next(item for item in refreshed if item["standard_role"] == "后端开发工程师")
        self.assertEqual(role_record["skills"], ["Python", "FastAPI"])


if __name__ == "__main__":
    unittest.main()
