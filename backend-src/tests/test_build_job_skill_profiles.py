import importlib.util
import math
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_job_skill_profiles.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_job_skill_profiles", SCRIPT_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class JobSkillProfileTests(unittest.TestCase):
    def make_job(
        self,
        job_id: str,
        family: str,
        skills: list[str],
        new_skills: list[str] | None = None,
    ):
        return {
            "job_id": job_id,
            "job_family": family,
            "skills": skills,
            "new_skills": new_skills or [],
        }

    def test_support_idf_categories_and_evidence(self):
        jobs = [
            self.make_job("a1", "AI工程师", ["Python", "RAG", "RAG"], ["RAG"]),
            self.make_job("a2", "AI工程师", ["Python", "RAG"], ["RAG"]),
            self.make_job("a3", "AI工程师", ["Python", "Agent"]),
            self.make_job("b1", "后端工程师", ["Python", "Java"]),
            self.make_job("b2", "后端工程师", ["Java", "SQL"]),
            self.make_job("b3", "后端工程师", ["Java", "SQL"]),
        ]
        config = MODULE.ProfileConfig(
            min_family_jobs=2,
            core_support=0.60,
            bonus_support=0.30,
            new_skill_support=0.50,
            top_k=10,
            evidence_limit=2,
        )

        result = MODULE.build_profiles(jobs, config)
        ai_profile = next(
            item
            for item in result["profiles"]
            if item["job_family"] == "AI工程师"
        )
        rag = next(
            item
            for item in ai_profile["distinctive_skills"]
            if item["skill"] == "RAG"
        )
        python = next(
            item
            for item in ai_profile["distinctive_skills"]
            if item["skill"] == "Python"
        )

        self.assertEqual(rag["job_count"], 2)
        self.assertAlmostEqual(rag["support"], 2 / 3, places=6)
        self.assertEqual(rag["evidence_job_ids"], ["a1", "a2"])
        self.assertGreater(rag["idf"], python["idf"])
        self.assertGreater(rag["distinctive_score"], 2 / 3)
        self.assertIn(
            "RAG", [item["skill"] for item in ai_profile["core_skills"]]
        )
        self.assertIn(
            "Agent", [item["skill"] for item in ai_profile["bonus_skills"]]
        )
        self.assertIn(
            "RAG",
            [item["skill"] for item in ai_profile["new_skill_signals"]],
        )

    def test_missing_and_small_families_are_reported(self):
        jobs = [
            self.make_job("a1", "AI工程师", ["Python"]),
            self.make_job("a2", "AI工程师", ["RAG"]),
            self.make_job("x1", "稀有岗位", ["量子计算"]),
            self.make_job("m1", "", ["SQL"]),
        ]
        config = MODULE.ProfileConfig(min_family_jobs=2)

        result = MODULE.build_profiles(jobs, config)

        self.assertEqual(result["summary"]["observed_job_families"], 2)
        self.assertEqual(result["summary"]["profiled_job_families"], 1)
        self.assertEqual(result["summary"]["families_below_minimum"], 1)
        self.assertEqual(result["summary"]["jobs_missing_family"], 1)

    def test_idf_formula_matches_smoothed_definition(self):
        payload = MODULE.skill_payload(
            skill="RAG",
            count=3,
            family_job_count=4,
            family_document_frequency=1,
            family_count=5,
            evidence=["a1"],
            new_skill_count=1,
        )

        expected_idf = math.log((5 + 1) / (1 + 1)) + 1
        self.assertAlmostEqual(payload["idf"], expected_idf, places=6)
        self.assertAlmostEqual(
            payload["distinctive_score"],
            0.75 * expected_idf,
            places=6,
        )


if __name__ == "__main__":
    unittest.main()
