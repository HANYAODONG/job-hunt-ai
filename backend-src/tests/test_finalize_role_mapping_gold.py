import json
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.finalize_role_mapping_gold import build


class FinalizeRoleMappingGoldTests(unittest.TestCase):
    def test_finalizes_existing_and_new_role_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates = root / "candidates.jsonl"
            annotations = root / "annotations.csv"
            candidates.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in [
                {"case_id": "case_1", "proposed_canonical_role_id": "backend_engineering"},
                {"case_id": "case_2", "proposed_canonical_role_id": "data_analysis"},
            ]), encoding="utf-8")
            annotations.write_text(
                "case_id,review_decision,final_canonical_role_id,new_role_candidate_name,review_evidence\n"
                "case_1,accept_proposal,backend_engineering,,后端服务职责\n"
                "case_2,new_role_candidate,,数据科学家,实验与因果推断职责\n",
                encoding="utf-8",
            )

            report = build(candidates, annotations, root / "out")
            rows = [json.loads(line) for line in (root / "out" / "role_mapping_gold_v1.jsonl").read_text(encoding="utf-8").splitlines()]

        self.assertEqual(report["records"], 2)
        self.assertEqual(rows[0]["final_canonical_role"], "后端开发工程师")
        self.assertEqual(rows[1]["new_role_candidate_name"], "数据科学家")
        self.assertEqual(rows[1]["label_status"], "requires_human_signoff_before_external_claims")


if __name__ == "__main__":
    unittest.main()
