import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.canonical_role_pool import CanonicalRolePool
from scripts.build_canonical_role_pool import adapt_enterprise_csv, build


class CanonicalRolePoolTests(unittest.TestCase):
    def setUp(self):
        self.pool = CanonicalRolePool()

    def test_language_specific_backend_roles_share_one_canonical_role(self):
        java = self.pool.classify({"standard_job": "Java开发工程师", "title": "Java后端开发工程师"})
        go = self.pool.classify({"standard_job": "Go开发工程师", "title": "Go服务端工程师"})

        self.assertEqual(java["canonical_role_id"], "backend_engineering")
        self.assertEqual(go["canonical_role_id"], "backend_engineering")
        self.assertEqual(java["role_specialization"], "Java")
        self.assertEqual(go["role_specialization"], "Go")

    def test_unmapped_roles_are_never_silently_admitted(self):
        result = self.pool.classify({"standard_job": "量子计算工程师", "title": "量子计算工程师"})

        self.assertEqual(result["role_mapping_status"], "unmapped")
        self.assertEqual(result["role_mapping_confidence"], 0.0)

    def test_non_technical_solution_title_requires_review(self):
        result = self.pool.classify({"standard_job": "解决方案工程师", "title": "客户经理"})

        self.assertEqual(result["role_mapping_status"], "review_required")
        self.assertIn("岗位标题包含非技术职能信号", result["role_mapping_review_reasons"])

    def test_generic_source_role_is_refined_only_by_strong_title_evidence(self):
        refined = self.pool.classify({"standard_job": "软件开发工程师", "title": "Go 后端开发工程师"})
        unresolved = self.pool.classify({"standard_job": "软件开发工程师", "title": "高级研发工程师"})

        self.assertEqual(refined["canonical_role_id"], "backend_engineering")
        self.assertTrue(refined["role_mapping_refined_by_title"])
        self.assertEqual(refined["role_mapping_status"], "mapped")
        self.assertEqual(unresolved["role_mapping_status"], "review_required")
        self.assertTrue(any(
            "规范岗位尚未激活" in reason
            for reason in unresolved["role_mapping_review_reasons"]
        ))

    def test_generic_source_role_can_use_multiple_skill_signals(self):
        result = self.pool.classify({
            "standard_job": "软件开发工程师",
            "title": "高级研发工程师",
            "skills": ["Java", "Spring Boot", "Redis", "MySQL"],
        })

        self.assertEqual(result["canonical_role_id"], "backend_engineering")
        self.assertTrue(result["role_mapping_refined_by_skills"])
        self.assertEqual(result["role_mapping_status"], "mapped")

    def test_enrich_preserves_provider_label_and_sets_graph_taxonomy(self):
        result = self.pool.enrich({"standard_job": "数据开发工程师", "title": "流式数据开发工程师"})

        self.assertEqual(result["source_standard_job"], "数据开发工程师")
        self.assertEqual(result["standard_job"], "数据工程师")
        self.assertEqual(result["standard_category"], "数据智能")
        self.assertEqual(result["standard_direction"], "数据工程与治理")

    def test_generic_source_labels_are_review_only_not_market_roles(self):
        self.assertEqual(self.pool.roles["general_algorithm"].status, "review_only")
        self.assertEqual(self.pool.roles["general_software_engineering"].status, "review_only")
        self.assertEqual(self.pool.roles["backend_engineering"].role_name, "后端开发工程师")

    def test_data_group_csv_adapter_preserves_source_label_and_skill_union(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job_bigcompany_final.csv"
            path.write_text(
                "job_id,job_title,standard_job,skills,traditional_skills,new_skills,job_responsibility\n"
                "JOB001,Java服务端工程师,Java开发工程师,Java;Spring,MySQL,Redis,负责服务端开发\n",
                encoding="utf-8",
            )
            record = next(adapt_enterprise_csv(path))

        self.assertEqual(record["source"], "data_group_job_bigcompany_final")
        self.assertEqual(record["standard_job"], "Java开发工程师")
        self.assertEqual(record["skills"], ["Java", "Spring", "MySQL", "Redis"])

    def test_neighbour_roles_receive_partial_not_full_credit(self):
        result = self.pool.relation_between("recommendation_algorithm", "advertising_algorithm")

        self.assertEqual(result["relation"], "related_specialization")
        self.assertEqual(result["matching_treatment"], "partial_credit")
        self.assertEqual(
            self.pool.relation_between("recommendation_algorithm", "recommendation_algorithm"),
            {"relation": "same_role", "matching_treatment": "full_credit"},
        )

    def test_build_report_distinguishes_core_catalog_from_observed_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "enterprise.jsonl"
            input_path.write_text(
                '{"job_id":"JOB001","title":"Java后端开发工程师","standard_job":"Java开发工程师","source_type":"enterprise"}\n',
                encoding="utf-8",
            )
            report = build(input_path, root / "output")

        self.assertEqual(report["role_catalog"]["scope"], "source-bounded_core_not_complete_market_catalog")
        self.assertEqual(report["role_catalog"]["defined_by_status"]["review_only"], 2)
        self.assertEqual(report["role_catalog"]["observed_active_role_identities"], 1)

    def test_market_verified_roles_have_strong_boundaries(self):
        navigation = self.pool.classify({
            "standard_job": "算法工程师",
            "title": "组合导航算法工程师",
            "skills": ["GNSS", "INS", "IMU", "卡尔曼滤波"],
        })
        data_scientist = self.pool.classify({
            "standard_job": "数据分析师",
            "title": "数据科学家",
            "skills": ["SQL", "实验设计", "统计推断", "因果推断"],
        })
        security_ops = self.pool.classify({
            "standard_job": "网络安全工程师",
            "title": "安全运营工程师",
            "skills": ["SOC", "SIEM", "告警研判", "应急响应"],
        })
        technical_artist = self.pool.classify({
            "standard_job": "软件开发工程师",
            "title": "游戏技术美术",
            "skills": ["Unity", "Shader", "美术工具"],
        })
        hvac = self.pool.classify({
            "standard_job": "硬件工程师",
            "title": "数据中心暖通工程师",
            "skills": ["数据中心", "暖通", "DCIM", "PUE"],
        })
        product = self.pool.classify({
            "standard_job": "AI产品经理",
            "title": "智能硬件产品经理",
            "skills": ["硬件规格", "BOM", "量产"],
        })

        self.assertEqual(navigation["canonical_role_id"], "navigation_positioning_algorithm")
        self.assertEqual(data_scientist["canonical_role_id"], "data_scientist")
        self.assertEqual(security_ops["canonical_role_id"], "security_operations")
        self.assertEqual(technical_artist["canonical_role_id"], "game_technical_artist")
        self.assertEqual(hvac["canonical_role_id"], "data_center_hvac")
        self.assertEqual(product["canonical_role_id"], "smart_hardware_product")
        self.assertTrue(all(item["role_mapping_status"] == "mapped" for item in (
            navigation, data_scientist, security_ops, technical_artist, hvac, product,
        )))

    def test_security_operation_signal_does_not_match_socket_or_system_on_chip(self):
        socket_client = self.pool.classify({
            "standard_job": "网络安全工程师",
            "title": "客户端开发工程师",
            "skills": ["Socket", "CocoaPods", "iOS", "Swift"],
        })
        soc_chip = self.pool.classify({
            "standard_job": "安全工程师",
            "title": "SoC验证工程师",
            "skills": ["SoC", "RTL", "功能验证"],
        })

        self.assertNotEqual(socket_client["canonical_role_id"], "security_operations")
        self.assertNotEqual(soc_chip["canonical_role_id"], "security_operations")


if __name__ == "__main__":
    unittest.main()
