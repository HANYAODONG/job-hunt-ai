from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest


def _source_item(store):
    return store.create_review_item(
        review_id="job-review-1",
        review_type="job",
        submission_mode="manual",
        job_id="source-jd-1",
        input_payload={
            "job_title": "智能体评测工程师",
            "responsibility": "设计智能体评测集和质量指标",
            "requirement": "熟悉 Python、LLM 和评测方法",
            "month": "2026-09",
        },
        result_payload={
            "route": {"status": "potential_new_job", "reason": "未命中现有岗位"},
            "skills": [{"normalized_skill": "Python", "raw_skill": "Python"}],
        },
    )


def test_discovery_workflow_exposes_source_and_waits_for_publish(monkeypatch, tmp_path):
    import app.services.discovery_service as discovery
    import app.services.job_service as jobs
    from job_update.company_job_update.core.database import SQLiteJobUpdateStore

    database = tmp_path / "updates.sqlite"
    monkeypatch.setattr(discovery, "BASE_DATABASE", database)
    monkeypatch.setattr(jobs, "BASE_DATABASE", database)
    store = SQLiteJobUpdateStore(database)
    source = _source_item(store)

    candidates = discovery.list_candidates()
    assert candidates[0]["candidate_id"] == source["item_id"]
    assert candidates[0]["stage"] == "candidate"
    assert candidates[0]["source"]["job_title"] == "智能体评测工程师"

    submitted = discovery.submit_proposal(
        source["item_id"],
        {
            "standard_category": "AI 测试与评测",
            "standard_job_title": "智能体评测工程师",
            "match_keywords": "智能体评测,LLM 评测",
            "required_skills": ["Python", "LLM 评测"],
            "core_responsibilities": ["设计评测集"],
        },
    )
    assert submitted["status"] == "submitted_dictionary_maintenance"
    maintenance_id = submitted["result"]["dictionary_maintenance_review_id"]
    waiting = discovery.list_candidates()
    assert waiting[0]["stage"] == "awaiting_publish"
    assert waiting[0]["maintenance_id"] == maintenance_id

    discovery.reject_candidate(maintenance_id)
    assert discovery.list_candidates() == []


def test_publish_updates_dictionary_and_both_review_records(monkeypatch, tmp_path):
    import app.services.discovery_service as discovery
    import app.services.job_service as jobs
    from job_update.company_job_update.core.database import SQLiteJobUpdateStore

    database = tmp_path / "updates.sqlite"
    dictionary = tmp_path / "standard_job_title_dictionary.csv"
    dictionary.write_text(
        "standard_job_title,standard_category,match_keywords\n旧岗位,研发,旧岗位\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(discovery, "BASE_DATABASE", database)
    monkeypatch.setattr(discovery, "BASE_TITLE_DICTIONARY", dictionary)
    monkeypatch.setattr(jobs, "BASE_DATABASE", database)
    monkeypatch.setattr(jobs, "BASE_TITLE_DICTIONARY", dictionary)
    store = SQLiteJobUpdateStore(database)
    source = _source_item(store)
    submitted = discovery.submit_proposal(
        source["item_id"],
        {"standard_category": "AI 测试与评测", "standard_job_title": "智能体评测工程师"},
    )
    maintenance_id = submitted["result"]["dictionary_maintenance_review_id"]

    class FakeSystem:
        def process(self, posting, **kwargs):
            assert kwargs["confirmed_standard_job"] == "智能体评测工程师"
            return SimpleNamespace(
                route=SimpleNamespace(),
                posting=posting,
                update=SimpleNamespace(normalized_skills=[]),
                normalized_skills=[],
                admissions=[],
            )

    monkeypatch.setattr(discovery, "_build_system", lambda progress: FakeSystem())
    monkeypatch.setattr(discovery, "_merge_summary", lambda result: {"event_rows": 1})
    monkeypatch.setattr(discovery, "serialize_review_process_result", lambda result, **kwargs: {"route": {}})
    monkeypatch.setattr(discovery, "_record_live_effect", lambda **kwargs: {"effect_id": "effect-1"})
    monkeypatch.setattr(discovery, "create_backup", lambda label: {"label": label})
    monkeypatch.setattr(discovery, "skill_mentions_from_decisions", lambda skills: [])

    published = discovery.publish_candidate(maintenance_id)
    assert published["status"] == "published_new_job"
    assert "智能体评测工程师" in dictionary.read_text(encoding="utf-8-sig")
    assert store.get_review_item(source["item_id"])["status"] == "merged_new_job"
    assert discovery.list_candidates()[0]["stage"] == "published"


def test_cluster_proposal_publishes_every_linked_jd(monkeypatch, tmp_path):
    import app.services.discovery_service as discovery
    import app.services.job_service as jobs
    from job_update.company_job_update.core.database import SQLiteJobUpdateStore

    database = tmp_path / "updates.sqlite"
    dictionary = tmp_path / "standard_job_title_dictionary.csv"
    dictionary.write_text("standard_job_title,standard_category,match_keywords\n旧岗位,研发,旧岗位\n", encoding="utf-8-sig")
    monkeypatch.setattr(discovery, "BASE_DATABASE", database)
    monkeypatch.setattr(discovery, "BASE_TITLE_DICTIONARY", dictionary)
    monkeypatch.setattr(jobs, "BASE_DATABASE", database)
    monkeypatch.setattr(jobs, "BASE_TITLE_DICTIONARY", dictionary)
    store = SQLiteJobUpdateStore(database)
    first = _source_item(store)
    second = store.create_review_item(
        review_id="job-review-2",
        review_type="job",
        submission_mode="manual",
        job_id="source-jd-2",
        input_payload={"job_title": "智能体评测工程师", "month": "2026-09"},
        result_payload={"route": {"status": "potential_new_job"}, "skills": []},
    )
    submitted = jobs.confirm_new_job(
        first["item_id"],
        standard_category="AI 测试与评测",
        standard_job_title="智能体评测工程师",
        match_keywords="智能体评测",
        merge_database=True,
        source_review_ids=[first["item_id"], second["item_id"]],
    )
    maintenance_id = submitted["result"]["dictionary_maintenance_review_id"]

    processed = []
    class FakeSystem:
        def process(self, posting, **kwargs):
            processed.append(posting.job_id)
            return SimpleNamespace(route=SimpleNamespace(), posting=posting, update=SimpleNamespace(normalized_skills=[]), normalized_skills=[], admissions=[])

    monkeypatch.setattr(discovery, "_build_system", lambda progress: FakeSystem())
    monkeypatch.setattr(discovery, "_merge_summary", lambda result: {"event_rows": 1})
    monkeypatch.setattr(discovery, "serialize_review_process_result", lambda result, **kwargs: {"route": {}})
    monkeypatch.setattr(discovery, "_record_live_effect", lambda **kwargs: {"effect_id": "effect-1"})
    monkeypatch.setattr(discovery, "create_backup", lambda label: {"label": label})
    monkeypatch.setattr(discovery, "skill_mentions_from_decisions", lambda skills: [])

    published = discovery.publish_candidate(maintenance_id)

    assert published["result"]["published_result"]["source_count"] == 2
    assert set(processed) == {"source-jd-1", "source-jd-2"}
    assert store.get_review_item(first["item_id"])["status"] == "merged_new_job"
    assert store.get_review_item(second["item_id"])["status"] == "merged_new_job"


def test_batch_summary_replays_role_pool_growth_separately_from_candidates(monkeypatch, tmp_path):
    import app.services.discovery_service as discovery

    event_stream = tmp_path / "job_update_event_stream.csv"
    event_stream.write_text(
        "job_id,month,standard_job,job_title,skills\n"
        "JD001,2026-07,后端开发工程师,Java 后端开发,Java; Spring\n"
        "JD002,2026-07,大模型应用工程师,智能体应用开发,LLM; RAG\n"
        "JD003,2026-08,数据分析师,经营数据分析,SQL; BI\n",
        encoding="utf-8-sig",
    )
    monkeypatch.setattr(discovery, "BASE_EVENT_STREAM", event_stream)
    monkeypatch.setattr(discovery, "BASE_DATABASE", tmp_path / "updates.sqlite")

    summary = discovery.batch_summary("2026-07", threshold=10, standard_job="后端开发工程师")

    assert summary["input_jd_count"] == 2
    assert summary["classified_jd_count"] == 2
    assert summary["cluster_count"] == 0
    assert summary["role_pool_evolution"]["first_month_role_count"] == 2
    assert summary["role_pool_evolution"]["new_role_count"] == 2
    assert summary["role_pool_evolution"]["cumulative_role_count"] == 2
    assert summary["role_pool_evolution"]["history"][1]["new_role_count"] == 1
    profile = summary["role_profile_evolution"]
    assert profile["standard_job"] == "后端开发工程师"
    assert profile["history"][0]["jd_count"] == 1
    assert profile["history"][0]["sample_titles"] == ["Java 后端开发"]


def test_batch_summary_groups_source_candidates_by_title(monkeypatch, tmp_path):
    import app.services.discovery_service as discovery
    from job_update.company_job_update.core.database import SQLiteJobUpdateStore

    event_stream = tmp_path / "job_update_event_stream.csv"
    event_stream.write_text(
        "job_id,month,standard_job,job_title,skills\n"
        "JD001,2026-08,,边缘智能体编排工程师,端云协同\n",
        encoding="utf-8-sig",
    )
    database = tmp_path / "updates.sqlite"
    store = SQLiteJobUpdateStore(database)
    for index in range(11):
        store.create_review_item(
            review_id=f"review-{index}",
            review_type="job",
            submission_mode="manual",
            job_id=f"SYN-{index:03d}",
            input_payload={"job_title": "边缘智能体编排工程师", "month": "2026-08"},
            result_payload={"route": {"status": "potential_new_job", "reason": "未命中现有岗位"}},
        )
    monkeypatch.setattr(discovery, "BASE_EVENT_STREAM", event_stream)
    monkeypatch.setattr(discovery, "BASE_DATABASE", database)

    summary = discovery.batch_summary("2026-08", threshold=10)

    assert summary["cluster_count"] == 1
    assert summary["candidates"][0]["title"] == "边缘智能体编排工程师"
    assert summary["candidates"][0]["supporting_jd_count"] == 11
    assert summary["candidates"][0]["source_count"] == 11
    assert len(summary["candidates"][0]["review_item_ids"]) == 11
    assert summary["candidates"][0]["threshold_met"] is True


def test_batch_summary_exposes_months_that_exist_only_in_review_queue(monkeypatch, tmp_path):
    import app.services.discovery_service as discovery
    from job_update.company_job_update.core.database import SQLiteJobUpdateStore

    database = tmp_path / "updates.sqlite"
    store = SQLiteJobUpdateStore(database)
    _source_item(store)
    monkeypatch.setattr(discovery, "BASE_DATABASE", database)
    monkeypatch.setattr(discovery, "BASE_EVENT_STREAM", tmp_path / "missing.csv")

    summary = discovery.batch_summary("2026-09", threshold=10)

    assert summary["available_months"] == ["2026-09"]
    assert summary["batch_status"] == "待人工审核"
    assert summary["input_jd_count"] == 1


def test_clear_imported_month_removes_only_unpublished_selected_batch(monkeypatch, tmp_path):
    import app.services.discovery_service as discovery
    from job_update.company_job_update.core.database import SQLiteJobUpdateStore

    database = tmp_path / "updates.sqlite"
    monkeypatch.setattr(discovery, "BASE_DATABASE", database)
    store = SQLiteJobUpdateStore(database)

    imported = store.create_review_item(
        review_id="imported-august",
        review_type="job",
        submission_mode="manual",
        job_id="web_202608_imported",
        input_payload={"month": "2026-08", "job_title": "边缘智能体编排工程师", "source": "monthly_csv_import", "import_kind": "monthly_csv", "import_batch_id": "monthly-csv-aug"},
        result_payload={"route": {"status": "potential_new_job"}},
    )
    store.create_review_item(
        review_id="imported-august-skill",
        review_type="skill",
        submission_mode="manual",
        job_id=imported["job_id"],
        parent_review_id=imported["item_id"],
        input_payload=imported["input"],
        result_payload={"skill": {"normalized_skill": "端云协同"}},
    )
    store.create_review_item(
        review_id="imported-august-proposal",
        review_type="dictionary_maintenance",
        submission_mode="manual",
        job_id=imported["job_id"],
        parent_review_id=imported["item_id"],
        input_payload=imported["input"],
        result_payload={"proposal_type": "new_standard_job", "source_job_review_ids": [imported["item_id"]]},
    )
    legacy = store.create_review_item(
        review_id="legacy-august",
        review_type="job",
        submission_mode="manual",
        job_id="web_202608_legacy",
        input_payload={"month": "2026-08", "job_title": "旧测试岗位", "source": "web_app_manual"},
        result_payload={"route": {"status": "potential_new_job"}},
    )
    september = store.create_review_item(
        review_id="imported-september",
        review_type="job",
        submission_mode="manual",
        job_id="web_202609_imported",
        input_payload={"month": "2026-09", "job_title": "九月岗位", "source": "monthly_csv_import", "import_kind": "monthly_csv"},
        result_payload={"route": {"status": "potential_new_job"}},
    )
    published = store.create_review_item(
        review_id="published-august",
        review_type="job",
        submission_mode="manual",
        status="merged_new_job",
        job_id="web_202608_published",
        input_payload={"month": "2026-08", "job_title": "已发布岗位", "source": "monthly_csv_import", "import_kind": "monthly_csv"},
        result_payload={"route": {"status": "potential_new_job"}},
    )

    result = discovery.clear_imported_month("2026-08")

    assert result == {
        "month": "2026-08",
        "deleted_review_items": 4,
        "deleted_candidates": 2,
        "deleted_maintenance_items": 1,
        "protected_shared_proposals": 0,
        "production_state_changed": False,
        "canonical_role_pool_changed": False,
        "event_stream_changed": False,
    }
    for review_id in [imported["item_id"], "imported-august-skill", "imported-august-proposal", legacy["item_id"]]:
        with pytest.raises(KeyError):
            store.get_review_item(review_id)
    assert store.get_review_item(september["item_id"])["status"] == "pending"
    assert store.get_review_item(published["item_id"])["status"] == "merged_new_job"


def test_clear_imported_month_rejects_non_month_input(monkeypatch, tmp_path):
    import app.services.discovery_service as discovery

    monkeypatch.setattr(discovery, "BASE_DATABASE", tmp_path / "updates.sqlite")
    with pytest.raises(ValueError, match="YYYY-MM"):
        discovery.clear_imported_month("August 2026")


def test_monthly_csv_import_stamps_a_clearable_batch(monkeypatch):
    import app.services.job_service as jobs

    submitted_payloads = []
    monkeypatch.setattr(
        jobs,
        "submit_one_dry_run",
        lambda payload: submitted_payloads.append(payload) or {"item_id": f"review-{len(submitted_payloads)}"},
    )

    result = jobs.import_csv(pd.DataFrame([
        {"month": "2026-08", "job_title": "边缘智能体编排工程师", "responsibility": "编排边缘智能体", "requirement": "任务调度"},
        {"month": "2026-09", "job_title": "智能体评测工程师", "responsibility": "构建评测集", "requirement": "Python"},
    ]))

    assert result["count"] == 2
    assert result["months"] == ["2026-08", "2026-09"]
    assert result["import_batch_id"].startswith("monthly-csv-")
    assert {payload["import_batch_id"] for payload in submitted_payloads} == {result["import_batch_id"]}
    assert {payload["source"] for payload in submitted_payloads} == {"monthly_csv_import"}
    assert {payload["import_kind"] for payload in submitted_payloads} == {"monthly_csv"}


def test_latest_live_evolution_returns_confirmed_effect(monkeypatch):
    """The live workspace must not fall back to an unreviewed routing candidate."""
    from app.api.endpoints import jd_update

    expected = {"effect_id": "effect-confirmed", "standard_job": "AI Infra 工程师"}
    monkeypatch.setattr(jd_update, "get_latest_live_update_effect", lambda domain: expected)

    assert jd_update.latest_live_evolution("company") == expected


def test_live_effect_ignores_frequency_only_drop_from_a_larger_jd_denominator():
    from app.services.live_update_effect_service import build_live_update_effect

    before = [
        {"skill": "CUDA", "monthly_skill_count": "13", "monthly_skill_frequency": "0.590909"},
        {"skill": "Go", "monthly_skill_count": "11", "monthly_skill_frequency": "0.5"},
    ]
    after = [
        {"skill": "CUDA", "monthly_skill_count": "13", "monthly_skill_frequency": "0.565217"},
        {"skill": "Go", "monthly_skill_count": "12", "monthly_skill_frequency": "0.521739"},
        {"skill": "Agent", "monthly_skill_count": "1", "monthly_skill_frequency": "0.043478"},
    ]

    effect = build_live_update_effect(
        standard_job="AI Infra 工程师",
        standard_category="AI 基础设施",
        month="2026-07",
        before_profile=before,
        after_profile=after,
        submitted_skills=["Agent"],
    )

    assert [row["skill"] for row in effect["changes"]["added"]] == ["Agent"]
    assert [row["skill"] for row in effect["changes"]["increased"]] == ["Go"]
    assert effect["changes"]["decreased"] == []
