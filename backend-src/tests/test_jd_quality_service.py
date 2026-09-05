from app.services.jd_quality_service import JdQualityService
import app.services.jd_quality_service as jd_quality_module
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class JdQualityServiceTest(unittest.TestCase):
    def test_jd_quality_detects_inflated_junior_role(self):
        service = JdQualityService()
        result = service.audit_job(
            {
                "job_id": "TEST-001",
                "title": "Junior Full Stack AI Engineer",
                "description": (
                    "Entry role requiring Python, Java, React, Kubernetes, AWS, Spark, "
                    "LLM, RAG, security, strong communication, and 5 years experience."
                ),
                "skills": ["Python", "Java", "React", "Kubernetes", "AWS", "Spark", "LLM", "RAG", "Security"],
            }
        )

        self.assertIn(result["risk_level"], {"medium", "high"})
        self.assertGreater(result["inflation_score"], 0)
        self.assertIn(result["graph_policy"], {"hold_for_review", "downweight_and_trace"})
        self.assertTrue(result["suspected_inflated_skills"])

    def test_jd_quality_allows_focused_role_with_trace(self):
        service = JdQualityService()
        result = service.audit_job(
            {
                "job_id": "TEST-002",
                "title": "Backend Engineer",
                "description": (
                    "Build and maintain internal API services with Python, FastAPI, PostgreSQL, and Redis. "
                    "Work with product engineers to improve reliability, add tests, and document service behavior."
                ),
                "skills": ["Python", "FastAPI", "PostgreSQL", "Redis"],
            }
        )

        self.assertEqual(result["risk_level"], "low")
        self.assertEqual(result["graph_policy"], "allow_with_trace")
        self.assertGreater(result["confidence"], 0)
        self.assertIn("evidence_risk", result)

    def test_jd_quality_batch_summary_counts_items(self):
        service = JdQualityService()
        result = service.audit_batch(
            [
                {"job_id": "A", "title": "Backend Engineer", "description": "Python FastAPI Redis."},
                {
                    "job_id": "B",
                    "title": "Junior AI Platform Engineer",
                    "description": "Requires Python, Java, React, Spark, Kubernetes, AWS, LLM, RAG, security and 5 years experience.",
                },
            ]
        )

        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(len(result["items"]), 2)
        self.assertIn("overall_summary", result["summary"])

    def test_sample_loader_uses_full_pool_and_offset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rows = [{"job_id": f"JOB-{index:03d}", "title": f"岗位{index}"} for index in range(40)]
            (root / "jobs.jsonl").write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )
            with patch.object(jd_quality_module, "DATASET_ITERATION_ROOT", root):
                selected = JdQualityService().load_sample_jobs(limit=10, offset=10)

        self.assertEqual(len(selected), 10)
        self.assertEqual(selected[0]["job_id"], "JOB-010")
        self.assertEqual(selected[-1]["job_id"], "JOB-019")


if __name__ == "__main__":
    unittest.main()
