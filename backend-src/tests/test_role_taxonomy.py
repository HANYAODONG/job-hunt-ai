import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.endpoints.graph import build_standard_role_graph
from app.services.role_taxonomy import refine_standard_role, role_affinity, role_match_grade


class StandardRoleGraphTests(unittest.TestCase):
    def test_role_matching_gate_distinguishes_same_adjacent_and_cross_family(self):
        self.assertEqual(role_match_grade("大模型算法工程师", "大模型算法工程师"), 3)
        self.assertEqual(role_match_grade("测试开发工程师", "高级游戏测试工程师"), 3)
        self.assertEqual(role_match_grade("数据平台工程师", "大数据运维工程师"), 2)
        self.assertEqual(role_match_grade("前端开发工程师", "客户端开发工程师"), 1)
        self.assertEqual(role_match_grade("控制算法工程师", "招聘运营经理"), 0)
        self.assertEqual(role_affinity("AI应用工程师", "大模型应用后端工程师"), 0.8)

    def test_refines_data_analysis_labels_only_with_title_evidence(self):
        self.assertEqual(
            refine_standard_role("数据", "数据分析师", title="数据科学家-电商场景"),
            "数据科学家",
        )
        self.assertEqual(
            refine_standard_role("数据", "数据分析师", title="商业分析经理"),
            "商业分析师",
        )
        self.assertEqual(
            refine_standard_role("数据", "数据分析师", title="数据分析岗"),
            "数据分析师",
        )

    def test_refines_broad_labels_from_direct_title_evidence(self):
        self.assertEqual(
            refine_standard_role("AI应用", "AI应用工程师", title="AI Agent后端开发工程师"),
            "AI应用后端工程师",
        )
        self.assertEqual(
            refine_standard_role("AI应用", "大模型应用工程师", title="AI应用前端工程师"),
            "AI应用前端工程师",
        )
        self.assertEqual(
            refine_standard_role("测试质量", "测试工程师", title="大模型评测工程师"),
            "模型评测工程师",
        )
        self.assertEqual(
            refine_standard_role("AI安全", "AI安全工程师", title="大模型安全研发工程师"),
            "AI模型安全工程师",
        )
        self.assertEqual(
            refine_standard_role("产品", "AI产品经理", title="数据产品经理"),
            "数据产品经理",
        )
        self.assertEqual(
            refine_standard_role("软件研发", "软件开发工程师", title="大数据开发工程师"),
            "大数据开发工程师",
        )
        self.assertEqual(
            refine_standard_role("软件研发", "软件开发工程师", title="服务器开发工程师"),
            "服务器开发工程师",
        )
        self.assertEqual(
            refine_standard_role("AI基础设施", "AI Infra工程师", title="大模型推理系统工程师"),
            "大模型推理系统工程师",
        )
        self.assertEqual(
            refine_standard_role("AI基础设施", "AI Infra工程师", title="AI Infra平台研发工程师"),
            "大模型平台工程师",
        )
        self.assertEqual(
            refine_standard_role("AI算法", "算法工程师", title="强化学习算法工程师"),
            "强化学习算法工程师",
        )
        self.assertEqual(
            refine_standard_role("AI算法", "算法工程师", title="具身智能算法工程师"),
            "具身智能算法工程师",
        )
        self.assertEqual(
            refine_standard_role("基础设施", "云计算工程师", title="云数据库研发工程师"),
            "云数据库工程师",
        )

    def test_keeps_refined_data_roles_under_one_data_analysis_direction(self):
        graph = build_standard_role_graph([
            {"standard_category": "数据", "standard_role": "数据分析师", "skills": []},
            {"standard_category": "数据", "standard_role": "数据科学家", "skills": []},
            {"standard_category": "数据", "standard_role": "商业分析师", "skills": []},
        ])
        domain = next(node for node in graph["tree"]["children"] if node["label"] == "数据智能")
        direction = next(node for node in domain["children"] if node["label"] == "数据分析")
        self.assertEqual({node["label"] for node in direction["children"]}, {"数据分析师", "数据科学家", "商业分析师"})

    def test_groups_recruitment_data_without_exposing_raw_titles(self):
        graph = build_standard_role_graph([
            {"standard_category": "AI应用", "standard_role": "大模型应用工程师", "skills": ["RAG", "Agent"]},
            {"standard_category": "AI应用", "standard_role": "大模型应用工程师", "skills": ["RAG", "FastAPI"]},
            {"standard_category": "软件研发", "standard_role": "后端开发工程师", "skills": ["Python"]},
        ])

        ai_application = next(node for node in graph["tree"]["children"] if node["label"] == "AI应用")
        direction = ai_application["children"][0]
        role = direction["children"][0]

        self.assertEqual(direction["label"], "大模型与智能体应用")
        self.assertEqual(role["label"], "大模型应用工程师")
        self.assertEqual(role["count"], 2)
        self.assertEqual(role["skills"], ["RAG", "Agent", "FastAPI"])
        self.assertTrue(direction["is_single_role"])
        self.assertEqual(direction["taxonomy_status"], "当前数据暂不足以细分")
        self.assertEqual(graph["summary"]["roles"], 2)
        self.assertEqual(graph["summary"]["job_postings"], 3)
        self.assertEqual(graph["summary"]["single_role_families"], 2)

    def test_keeps_unmatched_government_technical_posts_in_review_queue(self):
        graph = build_standard_role_graph([
            {
                "standard_category": "政务技术岗位",
                "standard_direction": "政务数据与智能",
                "standard_role": "政务数据智能技术岗",
                "skills": [],
                "needs_review": True,
            },
        ])

        role = graph["tree"]["children"][0]["children"][0]["children"][0]
        self.assertTrue(role["needs_review"])
        self.assertEqual(graph["summary"]["needs_review"], 1)

    def test_merges_algorithm_source_categories_into_real_world_domain(self):
        graph = build_standard_role_graph([
            {"standard_category": "AI算法", "standard_role": "大模型算法工程师", "skills": []},
            {"standard_category": "算法", "standard_role": "推荐算法工程师", "skills": []},
            {"standard_category": "自动驾驶", "standard_role": "自动驾驶算法工程师", "skills": []},
        ])

        domain = graph["tree"]["children"][0]
        self.assertEqual(domain["label"], "算法与智能")
        self.assertEqual(graph["summary"]["roles"], 3)
        self.assertEqual({child["label"] for child in domain["children"]}, {
            "生成式与语言智能", "推荐、风控与搜索算法", "控制、自动驾驶与优化",
        })

    def test_taxonomy_never_collapses_to_single_direction_or_role(self):
        graph = build_standard_role_graph([
            {"standard_category": "AI应用", "standard_role": "大模型应用工程师", "skills": []},
            {"standard_category": "AI应用", "standard_role": "Agent应用工程师", "skills": []},
            {"standard_category": "AI应用", "standard_role": "AI应用前端工程师", "skills": []},
            {"standard_category": "AI应用", "standard_role": "AI应用后端工程师", "skills": []},
            {"standard_category": "数据", "standard_role": "数据分析师", "skills": []},
            {"standard_category": "数据", "standard_role": "数据科学家", "skills": []},
            {"standard_category": "数据", "standard_role": "数据开发工程师", "skills": []},
            {"standard_category": "数据", "standard_role": "数据工程师", "skills": []},
        ])

        for domain in graph["tree"]["children"]:
            self.assertGreaterEqual(len(domain["children"]), 2)
            for direction in domain["children"]:
                self.assertGreaterEqual(len(direction["children"]), 2)

    def test_filters_graph_snapshot_by_publish_year(self):
        records = [
            {
                "standard_category": "AI应用",
                "standard_role": "大模型应用工程师",
                "skills": ["RAG"],
                "publish_time": "2024-06-01",
            },
            {
                "standard_category": "数据",
                "standard_role": "数据工程师",
                "skills": ["Spark"],
                "publish_time": "2026/07/15",
            },
        ]

        graph_2024 = build_standard_role_graph(records, year=2024)
        graph_2026 = build_standard_role_graph(records, year=2026)

        self.assertEqual(graph_2024["summary"]["job_postings"], 1)
        self.assertEqual(graph_2026["summary"]["job_postings"], 1)
        self.assertEqual(graph_2024["tree"]["label"], "岗位银河 (2024)")
        self.assertEqual(graph_2026["tree"]["label"], "岗位银河 (2026)")

    def test_returns_empty_snapshot_for_year_without_records(self):
        graph = build_standard_role_graph([
            {
                "standard_category": "数据",
                "standard_role": "数据工程师",
                "skills": ["Python"],
                "publish_time": "2026-01-10",
            },
        ], year=2025)

        self.assertEqual(graph["summary"]["job_postings"], 0)
        self.assertEqual(graph["tree"]["children"], [])


if __name__ == "__main__":
    unittest.main()
