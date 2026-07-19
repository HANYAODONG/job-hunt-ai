# 第五次迭代：工作流 1 与 BM25 接入

## 输入

- `dataset/incoming/job_bigcompany_final.csv`
- `dataset/incoming/standard_job_title_dictionary.csv`
- `dataset/incoming/synthetic_detailed_resumes.csv`
- `dataset/incoming/resume_job_silver_30.jsonl`
- `dataset/incoming/金标30×20.csv`

## 工作流 1 输出

运行：

```powershell
python .\scripts\dataset_adapter.py
```

Label files are required by default to prevent accidental empty evaluation labels. For unlabeled smoke tests only:

```powershell
python .\scripts\dataset_adapter.py --allow-missing-labels
```

生成到 `artifacts/dataset_iteration_05/`：

- `jobs.jsonl`：12,675 条标准岗位。
- `candidate_profiles.jsonl`：5,500 份脱敏标准简历。
- `data_quality_report.json`：字段缺失和 ID 检查。
- `sample_pack/`：10 条岗位和 5 份简历。
- 空标签文件：当前仓库未提供金标和银标源文件。

质量检查：岗位和简历 ID 均无重复；岗位技能缺失 405 条；日期缺失 1,406 条，另有 43 条无效占位日期转为空；公司和地点因源 CSV 未提供而为空。

## BM25 输出

运行：

```powershell
docker compose up -d elasticsearch
python .\backend-src\scripts\index_chinese_jobs.py --recreate
python .\backend-src\scripts\retrieve_bm25_candidates.py --size 200
```

索引 `bigcompany_jobs_v1` 写入 12,675 条岗位，失败 0 条。候选集采用 batch JSONL，每行包含 `query_id`、`query_text`、查询耗时和候选数组；候选字段为 `job_id`、`bm25_score`、`bm25_rank`。

## 冒烟验证

- 人工后端查询 Top1 为标准后端开发岗位。
- 前 5 份简历均完成 Top20，共 100 个候选。
- 1 份简历完成 Top200，排名 1-200 连续。
- 算法、测试和移动开发样例的 Top5 基本符合目标岗位。
- 一份运维简历被测试类技能带偏，说明岗位族权重仍需评测调优。

## 尚未完成

- 工作流 1 尚未提供 `standard_job -> target_job_family` 对照表。
- 当前仓库没有金标/银标源文件，不能计算正式 MRR、NDCG 和 Recall。
- 中文分析器和字段权重仍是第一版 baseline，需要用 dev 集比较。
