import importlib.util
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "discover_emerging_jobs.py"
)
SPEC = importlib.util.spec_from_file_location("discover_emerging_jobs", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class EmergingJobDiscoveryTests(unittest.TestCase):
    def make_job(
        self,
        index: int,
        title: str,
        standard_job: str,
        skills: list[str],
        new_skills: list[str],
        publish_date: date,
    ):
        return {
            "job_id": f"job_{index}",
            "title": title,
            "normalized_title": title,
            "standard_job": standard_job,
            "responsibilities": f"负责{title}平台建设和技术方案落地",
            "requirements": f"熟悉{' '.join(skills)}",
            "description": f"{title} {' '.join(skills)}",
            "skills": skills,
            "traditional_skills": skills,
            "new_skills": new_skills,
            "domain_context": ["人工智能"],
            "publish_date": publish_date,
            "publish_time_raw": publish_date.isoformat(),
            "source": "test",
            "company": "测试公司",
        }

    def test_recent_novel_cluster_is_returned_with_evidence(self):
        today = date(2026, 7, 1)
        jobs = []
        for index in range(12):
            jobs.append(
                self.make_job(
                    index,
                    "量子提示工程师",
                    "软件开发工程师",
                    ["量子提示", "智能体编排", "Python"],
                    ["量子提示", "智能体编排"],
                    today - timedelta(days=index),
                )
            )
        for index in range(12, 24):
            jobs.append(
                self.make_job(
                    index,
                    "Java开发工程师",
                    "Java开发工程师",
                    ["Java", "Spring", "MySQL"],
                    [],
                    today - timedelta(days=500 + index),
                )
            )

        taxonomy = [
            {
                "name": "Java开发工程师",
                "category": "软件开发",
                "keywords": "Java|Spring|MySQL",
            }
        ]
        config = MODULE.DiscoveryConfig(
            clusters=2,
            min_cluster_size=5,
            recent_days=180,
            min_score=0.25,
            top_k=10,
            max_features=3_000,
            random_state=7,
            evidence_limit=3,
            max_cluster_share=1.0,
        )
        result = MODULE.discover(jobs, taxonomy, config)

        names = [item["candidate_name"] for item in result["candidates"]]
        self.assertIn("量子提示工程师", names)
        candidate = next(
            item
            for item in result["candidates"]
            if item["candidate_name"] == "量子提示工程师"
        )
        self.assertEqual(candidate["review_status"], "candidate_requires_human_review")
        self.assertGreaterEqual(candidate["supporting_jd_count"], 10)
        self.assertTrue(candidate["evidence"])
        self.assertIn(
            "量子提示",
            [item["name"] for item in candidate["definition"]["emerging_skills"]],
        )

    def test_date_parser_accepts_excel_style_epoch_milliseconds(self):
        parsed = MODULE.parse_date("1.78E+12")
        self.assertIsNotNone(parsed)
        self.assertGreaterEqual(parsed.year, 2026)

    def test_exact_reposts_are_deduplicated(self):
        today = date(2026, 7, 1)
        older = self.make_job(
            1,
            "智能体工程师",
            "大模型应用工程师",
            ["Agent", "RAG"],
            ["Agent"],
            today - timedelta(days=10),
        )
        newer = {**older, "job_id": "job_2", "publish_date": today}

        unique, duplicate_count = MODULE.deduplicate_jobs([older, newer])

        self.assertEqual(duplicate_count, 1)
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0]["job_id"], "job_2")


if __name__ == "__main__":
    unittest.main()
