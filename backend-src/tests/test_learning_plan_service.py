from __future__ import annotations

from app.services.learning_plan_service import build_learning_plan


def test_build_learning_plan_minimal_fields():
    plan = build_learning_plan(
        target_role="大模型应用工程师",
        missing_skills=[
            {"skill": "Agent 工作流", "priority": "high"},
            {"skill": "模型评测", "priority": "medium"},
            {"skill": "可观测性", "priority": "low"},
        ],
        candidate_name="陈同学",
        target_version="v1.2",
        match_score=0.72,
    )

    # 分工5 §7.3 要求的最小输出字段
    assert plan["target_role"] == "大模型应用工程师"
    assert isinstance(plan["missing_skills"], list)
    assert len(plan["missing_skills"]) == 3
    assert plan["stages"]
    assert plan["resources"]

    # 每个阶段都携带 priority / learning_stage / suggestion / resources
    for stage in plan["stages"]:
        assert stage["priority"] in {"high", "medium", "low"}
        assert stage["learning_stage"].startswith("阶段")
        assert stage["suggestion"]
        assert stage["resources"]

    # 新生成的计划：首个“进行中”，其余“未开始”
    assert plan["stages"][0]["status"] == "进行中"
    assert all(s["status"] == "未开始" for s in plan["stages"][1:])

    # 前端页面字段
    assert plan["profile"] == "陈同学"
    assert plan["target_version"] == "v1.2"
    assert plan["match_score"] == 0.72
    assert plan["progress"] > 0
    assert plan["current_stage"]
    assert plan["gap_count"] == 3


def test_build_learning_plan_sorts_by_priority():
    plan = build_learning_plan(
        target_role="数据工程师",
        missing_skills=[
            {"skill": "低优先级技能", "priority": "low"},
            {"skill": "高优先级技能", "priority": "high"},
            {"skill": "中优先级技能", "priority": "medium"},
        ],
    )

    priorities = [s["priority"] for s in plan["stages"]]
    assert priorities == ["high", "medium", "low"]


def test_build_learning_plan_normalizes_string_skills():
    plan = build_learning_plan(
        target_role="后端工程师",
        missing_skills=["Python", "FastAPI"],
    )

    assert [s["skill"] for s in plan["missing_skills"]] == ["Python", "FastAPI"]
    assert len(plan["stages"]) == 2
    # 字符串技能默认 high 优先级
    assert plan["stages"][0]["priority"] == "high"


def test_build_learning_plan_empty_skills():
    plan = build_learning_plan(target_role="前端工程师", missing_skills=[])
    assert plan["stages"] == []
    assert plan["gap_count"] == 0
    assert plan["progress"] == 0


def test_build_learning_plan_max_stages():
    plan = build_learning_plan(
        target_role="测试",
        missing_skills=[{"skill": f"技能{i}", "priority": "high"} for i in range(10)],
        max_stages=5,
    )
    assert len(plan["stages"]) == 5
