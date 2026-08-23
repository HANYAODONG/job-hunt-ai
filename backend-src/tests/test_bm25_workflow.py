import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DISABLE_EXTERNAL_SERVICES", "true")

from app.services.chinese_bm25_service import ChineseBM25Service
from app.api.endpoints import bm25 as bm25_endpoint


def load_script(name: str, scripts_root: Path = BACKEND_ROOT):
    path = scripts_root / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


retrieve_script = load_script("retrieve_bm25_candidates")
evaluate_script = load_script("evaluate_candidate_rankings", REPO_ROOT)


class FakeElasticsearch:
    def __init__(self):
        self.last_search = None

    def search(self, **kwargs):
        self.last_search = kwargs
        return {
            "took": 7,
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_score": 12.5,
                        "_source": {
                            "job_id": "JOB001",
                            "title": "后端开发工程师",
                            "source_type": "enterprise",
                        },
                    }
                ],
            },
        }


class BM25WorkflowTests(unittest.TestCase):
    def test_prepare_document_uses_canonical_fields(self):
        document = ChineseBM25Service.prepare_document(
            {
                "job_id": "JOB001",
                "title": "后端开发工程师",
                "standard_job": "后端开发工程师",
                "skills": ["Python", "Python", "Redis"],
                "new_skills": ["Agent"],
                "requirements": "熟悉Python与Redis",
            }
        )

        self.assertEqual(document["job_id"], "JOB001")
        self.assertEqual(document["skills"], ["Python", "Redis"])
        self.assertEqual(document["job_family"], "后端开发工程师")
        self.assertIn("Python", document["all_text"])

    def test_sample_action_limit_keeps_stable_job_ids(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.jsonl"
            path.write_text(
                "\n".join(
                    json.dumps({"job_id": f"JOB{index:03d}", "title": "测试岗位"}, ensure_ascii=False)
                    for index in range(3)
                ),
                encoding="utf-8",
            )
            actions = list(ChineseBM25Service(FakeElasticsearch()).iter_actions(path, limit=2))

        self.assertEqual([action["_id"] for action in actions], ["JOB000", "JOB001"])
        self.assertEqual(len(actions), 2)

    def test_search_builds_weighted_query_and_compact_hits(self):
        client = FakeElasticsearch()
        service = ChineseBM25Service(client)

        result = service.search(
            "后端 Python Redis",
            size=200,
            source_type="enterprise",
        )

        self.assertEqual(result["hits"][0]["rank"], 1)
        self.assertEqual(result["hits"][0]["score"], 12.5)
        bool_query = client.last_search["query"]["bool"]
        self.assertEqual(
            bool_query["filter"],
            [{"term": {"source_type": "enterprise"}}],
        )
        self.assertIn("standard_job^7", bool_query["must"][0]["multi_match"]["fields"])

    def test_query_text_is_structured_and_deduplicated(self):
        query = retrieve_script.build_query_text(
            {
                "target_job_family": "后端开发工程师",
                "skills": ["Python", "Redis", "Python"],
                "experience": [{"role": "后端开发工程师"}],
                "education": {"major": "计算机科学"},
                "years_experience": 3,
            }
        )

        self.assertEqual(query.count("Python"), 1)
        self.assertIn("后端开发工程师", query)
        self.assertIn("3年经验", query)

    def test_compact_candidate_endpoint_matches_team_contract(self):
        fake_result = {
            "index_name": "bigcompany_jobs_v1",
            "took_ms": 8,
            "total": 50,
            "hits": [
                {"job_id": "JOB001", "score": 9.2, "rank": 1, "title": "后端"}
            ],
        }
        request = bm25_endpoint.BM25CandidateRequest(
            query_id="resume_001",
            query="Python Redis",
            size=20,
        )
        with patch.object(
            bm25_endpoint,
            "execute_search",
            return_value=fake_result,
        ):
            response = bm25_endpoint.retrieve_candidates(request)

        self.assertEqual(response["query_id"], "resume_001")
        self.assertEqual(
            response["candidates"],
            [{"job_id": "JOB001", "bm25_score": 9.2, "bm25_rank": 1}],
        )

    def test_evaluator_computes_expected_perfect_metrics(self):
        ranking = {
            "resume_001": [
                {"job_id": "JOB001"},
                {"job_id": "JOB002"},
            ]
        }
        labels = {
            ("resume_001", "JOB001"): 3,
            ("resume_001", "JOB002"): 1,
        }

        report = evaluate_script.evaluate(ranking, labels, [1, 2], 2)

        aggregate = report["aggregate"]
        self.assertEqual(aggregate["evaluated_queries"], 1)
        self.assertEqual(aggregate["mrr"], 1.0)
        self.assertEqual(aggregate["recall@1"], 1.0)
        self.assertEqual(aggregate["ndcg@2"], 1.0)


if __name__ == "__main__":
    unittest.main()
