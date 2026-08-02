# 第十次迭代：接入 2024-2026 政府技术岗位数据

## 迭代原因

数据对接成员新增了 `government_jobs_2024_2026_tech_final.csv`。相比上一版 `government_jobs_2026_tech_filtered.csv`，新版政府岗位经过两轮筛选，数量约 3k，并且增加了年份字段，可以支持按 2024、2025、2026 年份分析。

如果继续使用旧政府岗位文件，第三阶段联调时会出现数据口径不一致：部分成员使用旧版 2026 单年岗位，部分成员使用 2024-2026 多年岗位，导致岗位总数、政府岗位 ID 和下游索引结果不一致。

## 迭代目的

本次迭代目标是将新版政府技术岗位纳入工作流 1 标准数据基座，并尽量保持对旧文件的兼容。

## 本次修改

1. 将 `government_jobs_2024_2026_tech_final.csv` 归入统一数据入口 `database/`。
2. 更新 `scripts/dataset_adapter.py`，优先读取新版政府岗位文件。
3. 继续保留旧文件 `government_jobs_2026_tech_filtered.csv` 作为 fallback。
4. 政府岗位标准 `job_id` 优先使用 `raw.job_uid`，避免用顺序号生成不稳定 ID。
5. 将 `raw.dataset_year` 写入标准岗位字段 `dataset_year`。
6. 将 `tech_filter.categories`、`tech_filter.reason`、`tech_filter.scope` 写入 `search_metadata`。
7. 更新 `docs/workflow-1-standard-dataset-usage.md`，说明新版政府岗位文件和年份字段。

## 新版生成结果

重新运行：

```powershell
python .\scripts\dataset_adapter.py
python .\scripts\validate_workflow1_dataset.py --output .\artifacts\dataset_iteration_05\validation_report.json
```

当前结果：

```text
jobs: 16574
candidate_profiles: 30200
jobs_enterprise: 12675
jobs_government: 3045
jobs_label_legacy: 854
label_pairs_gold: 600
label_pairs_silver: 6000
```

政府岗位年份分布：

```text
2024: 1020
2025: 1142
2026: 883
```

验收结果：

```text
gold missing refs: 0
silver missing refs: 0
duplicate government job IDs: 0
status: pass
```

## 对其他工作流的影响

- 第三阶段正式数据继续统一使用 `dataset_iteration_05`。
- 岗位总数从上一版 14583 增加到 16574。
- 政府岗位从上一版 1054 增加到 3045。
- 政府岗位 ID 由顺序生成的 `GOVxxxxx` 转为更稳定的原始 `job_uid`。
- BM25、语义重排、知识图谱和融合排序需要重新基于新版 `jobs.jsonl` 或 `jobs_government.jsonl` 生成本地索引/中间产物。
- 低配置电脑仍建议先使用 `sample_pack/` 做接口联调。

## 后续注意

新版政府岗位已经有年份字段，后续可以在前端或评估中加入“年份筛选”或“按年份对比岗位需求变化”。但第三阶段主线仍然优先保证全链路跑通，不建议现在额外扩展复杂分析页面。
