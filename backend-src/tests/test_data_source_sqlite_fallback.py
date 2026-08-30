from __future__ import annotations

import sqlite3

import pandas as pd

from app.services import data_source_service


def test_base_tables_fall_back_to_runtime_sqlite(monkeypatch, tmp_path):
    database = tmp_path / "job_update.db"
    tables = {
        "job_skill_monthly_frequency": pd.DataFrame(
            [
                {
                    "month": "2026-07",
                    "standard_job": "后端开发工程师",
                    "skill": "Python",
                    "monthly_jd_count": 10,
                    "monthly_skill_count": 8,
                    "monthly_skill_frequency": 0.8,
                    "cumulative_jd_count": 10,
                    "cumulative_skill_count": 8,
                    "cumulative_skill_frequency": 0.8,
                    "rank_in_month": 1,
                    "is_core_skill": 1,
                }
            ]
        ),
        "skill_lifecycle": pd.DataFrame([{"skill": "Python", "lifecycle_status": "活跃技能"}]),
        "skill_migration": pd.DataFrame([{"skill": "Python", "spread_job_count": 1}]),
        "skill_job_monthly_spread": pd.DataFrame(
            [{"month": "2026-07", "standard_job": "后端开发工程师", "skill": "Python"}]
        ),
        "job_profile_snapshots": pd.DataFrame(
            [
                {
                    "month": "2026-07",
                    "standard_job": "后端开发工程师",
                    "skill": "Python",
                    "monthly_jd_count": 10,
                    "monthly_skill_count": 8,
                    "monthly_skill_frequency": 0.8,
                    "cumulative_jd_count": 10,
                    "cumulative_skill_count": 8,
                    "cumulative_skill_frequency": 0.8,
                    "rank_in_month": 1,
                    "is_core_skill": 1,
                }
            ]
        ),
        "job_profile_diff": pd.DataFrame(
            [{"from_month": "2026-06", "to_month": "2026-07", "skill": "Python"}]
        ),
    }
    with sqlite3.connect(database) as connection:
        for name, frame in tables.items():
            frame.to_sql(name, connection, index=False)

    missing_csvs = [tmp_path / f"missing_{index}.csv" for index in range(7)]
    monkeypatch.setattr(data_source_service, "_base_table_paths", lambda _domain: missing_csvs)
    monkeypatch.setattr(data_source_service, "_base_database_path", lambda _domain: database)

    frequency, lifecycle, migration, spread, snapshots, diff, current = (
        data_source_service._read_base_tables("company")
    )

    assert len(frequency) == 1
    assert len(lifecycle) == 1
    assert len(migration) == 1
    assert len(spread) == 1
    assert len(snapshots) == 1
    assert len(diff) == 1
    assert current.iloc[0]["standard_job"] == "后端开发工程师"
    assert current.iloc[0]["skill"] == "Python"
