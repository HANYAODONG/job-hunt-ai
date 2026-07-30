# 第九次迭代：工作流 1 数据基座收尾

## 迭代原因

第三阶段即将进入全链路联调，其他工作流需要稳定读取工作流 1 的标准数据。如果数据版本、ID 映射、标签引用和验收命令没有固定，后续 BM25、语义重排、知识图谱和融合排序会反复出现字段不一致、评估全为 0、样本无法复现等问题。

## 迭代目的

本次迭代的目标是把工作流 1 从“能生成数据”推进到“可交付、可验收、可供其他模块直接使用”。

## 本次修改

1. 将候选排序评估脚本默认目录统一到 `artifacts/dataset_iteration_05`。
2. 新增 `scripts/validate_workflow1_dataset.py`，用于快速检查工作流 1 产物是否完整。
3. 更新 `docs/data-schema.md`，将当前公共数据契约指向 `dataset_iteration_05`。
4. 更新 `docs/workflow-1-standard-dataset-usage.md`，补充生成后的验收命令和第三阶段最低交付。

## 验收脚本检查内容

`validate_workflow1_dataset.py` 会检查：

- 标准岗位、标准简历、金标、银标是否存在。
- `data_quality_report.json` 和 `dataset_manifest.json` 是否存在。
- `sample_pack/` 是否存在并包含小样本文件。
- `candidate_id` 和 `job_id` 是否重复。
- 金标、银标中的 `candidate_id` 和 `job_id` 是否能在标准数据中找到。
- 关键字段是否缺失。
- 标签等级分布和岗位来源分布。

## 标准运行命令

```powershell
cd "D:\Desktop\挑战杯大模型组\job-hunt-ai-main"
python .\scripts\dataset_adapter.py
python .\scripts\validate_workflow1_dataset.py --output .\artifacts\dataset_iteration_05\validation_report.json
```

## 当前工作流 1 对外交付

```text
artifacts/dataset_iteration_05/jobs.jsonl
artifacts/dataset_iteration_05/candidate_profiles.jsonl
artifacts/dataset_iteration_05/label_pairs_gold.jsonl
artifacts/dataset_iteration_05/label_pairs_silver.jsonl
artifacts/dataset_iteration_05/sample_pack/
artifacts/dataset_iteration_05/data_quality_report.json
artifacts/dataset_iteration_05/validation_report.json
```

## 后续注意

- `artifacts/` 中的大规模产物默认不提交到仓库。
- 如果数据集小组重新生成新版金银标，应优先使用标准 `candidate_id` 和 `job_id`，不要继续依赖旧版 legacy ID。
- 其他工作流必须先使用 `sample_pack/` 联调，避免一开始就因全量数据过大导致开发受阻。
