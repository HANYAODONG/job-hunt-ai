import json
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_role_mapping_gold_candidates import build


class RoleMappingGoldCandidateTests(unittest.TestCase):
    def test_builds_role_coverage_and_keeps_matching_gold_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "canonical.jsonl"
            review = root / "review.jsonl"
            gold = root / "gold.jsonl"
            legacy = root / "legacy.jsonl"
            canonical.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in [
                {"job_id": "J1", "title": "后端开发", "canonical_role_id": "backend", "canonical_role": "后端开发工程师", "canonical_domain": "软件工程", "canonical_direction": "服务端", "role_mapping_status": "mapped"},
                {"job_id": "J2", "title": "数据工程", "canonical_role_id": "data", "canonical_role": "数据工程师", "canonical_domain": "数据智能", "canonical_direction": "数据工程", "role_mapping_status": "mapped"},
            ]), encoding="utf-8")
            review.write_text(json.dumps({"job_id": "J3", "title": "通用开发", "role_mapping_status": "review_required", "role_mapping_review_reasons": ["需裁决"]}, ensure_ascii=False), encoding="utf-8")
            gold.write_text(json.dumps({"candidate_id": "C1", "job_id": "J3", "grade": 3}, ensure_ascii=False), encoding="utf-8")
            legacy.write_text(json.dumps({"job_id": "J3"}, ensure_ascii=False), encoding="utf-8")

            report = build(canonical, review, gold, legacy, root / "out", target_count=3)
            cases = [json.loads(line) for line in (root / "out" / "role_mapping_gold_candidates.jsonl").read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(cases), 3)
        self.assertEqual({case["proposed_canonical_role_id"] for case in cases if case["proposed_canonical_role_id"]}, {"backend", "data"})
        self.assertTrue(all(not case["final_canonical_role_id"] for case in cases))
        self.assertTrue(report["not_role_mapping_gold"])
        self.assertEqual(report["job_id_overlap_with_current_canonical_jobs"], 0)
        self.assertEqual(report["mapped_role_identities_covered"], 2)


if __name__ == "__main__":
    unittest.main()
