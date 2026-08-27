import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "review_jd_quality_with_deepseek.py"
SPEC = importlib.util.spec_from_file_location("review_jd_quality_with_deepseek", SCRIPT_PATH)
reviewer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reviewer
SPEC.loader.exec_module(reviewer)


class JDQualityDeepSeekReviewTests(unittest.TestCase):
    def test_compact_job_does_not_leak_rule_prediction(self):
        row = {
            "job_id": "JOB1",
            "title": "Python工程师",
            "description_raw": "负责Python服务开发",
            "is_duplicate": True,
            "noise_score": 1.0,
        }
        compact = reviewer.compact_job(row, {"JOB1": row}, max_chars=200)

        self.assertNotIn("rule_prediction", compact)
        self.assertEqual(compact["current_jd"], "负责Python服务开发")

    def test_grounded_double_vote_creates_pseudo_human_gold(self):
        labels = {
            "duplicate": False,
            "noise": True,
            "inflation": False,
            "stale": False,
            "multi_source_verified": True,
        }
        vote = {
            "labels": labels,
            "confidence": 0.92,
            "evidence_valid": True,
            "needs_human_review": False,
        }
        row = {
            "job_id": "JOB1",
            "title": "Python工程师",
            "noise_score": 0.55,
            "verified_by_multi_source": True,
        }
        record = reviewer.aggregate(row, [dict(vote), dict(vote)], min_confidence=0.82)

        self.assertTrue(record["is_pseudo_human_gold"])
        self.assertEqual(record["llm_labels"], labels)


if __name__ == "__main__":
    unittest.main()
