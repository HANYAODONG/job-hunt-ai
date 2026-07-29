# 工作流 1：标准数据集生成说明

本文档说明组员如何使用工作流 1 脚本，把 `database/` 中的数据统一转换为各工作流可直接读取的标准 JSONL。

## 1. 目的

各工作流不要分别读取原始 CSV。统一由工作流 1 生成标准数据，后续 BM25、BGE、知识图谱、融合排序都读取同一批产物，避免字段名、ID、路径不一致。

## 2. 原始数据位置

请把数据放在项目同级的 `database/` 文件夹中：

```text
挑战杯大模型组/
├─ database/
│  ├─ job_bigcompany_final.csv
│  ├─ government_jobs_2026_tech_filtered.csv
│  ├─ synthetic_detailed_resumes_experience_30k.csv
│  ├─ standard_job_title_dictionary.csv
│  ├─ resume_job_silver_30.jsonl
│  └─ 金标30×20.csv
└─ job-hunt-ai-main/
```

文件作用：

| 文件 | 作用 |
| --- | --- |
| `job_bigcompany_final.csv` | 企业岗位主数据 |
| `government_jobs_2026_tech_filtered.csv` | 公务员/事业单位技术岗位 |
| `synthetic_detailed_resumes_experience_30k.csv` | 扩充后的 30k 简历数据 |
| `standard_job_title_dictionary.csv` | 岗位名称归一词典 |
| `resume_job_silver_30.jsonl` | 旧版银标，暂时用于兼容评估 |
| `金标30×20.csv` | 旧版金标，暂时用于兼容评估 |

## 3. 生成命令

在 PowerShell 中进入项目目录：

```powershell
cd "D:\Desktop\挑战杯大模型组\job-hunt-ai-main"
```

执行：

```powershell
python .\scripts\dataset_adapter.py
```

如果暂时没有金标/银标文件：

```powershell
python .\scripts\dataset_adapter.py --allow-missing-labels
```

如果只想生成企业岗位，不加入公务员岗位：

```powershell
python .\scripts\dataset_adapter.py --skip-government
```

## 4. 输出位置

默认输出到：

```text
job-hunt-ai-main/artifacts/dataset_iteration_05/
```

主要产物：

| 文件 | 下游用途 |
| --- | --- |
| `jobs.jsonl` | 全量岗位，包含企业岗位、公务员技术岗位、旧标签 legacy 岗位 |
| `jobs_enterprise.jsonl` | 企业岗位子集 |
| `jobs_government.jsonl` | 公务员/事业单位技术岗位子集 |
| `jobs_label_legacy.jsonl` | 从旧金银标中抽出的 legacy 岗位，用于旧标签对齐 |
| `candidate_profiles.jsonl` | 标准简历/候选人画像 |
| `label_pairs_silver.jsonl` | 标准银标匹配对 |
| `label_pairs_gold.jsonl` | 标准金标匹配对 |
| `data_quality_report.json` | 数据质量检查报告 |
| `dataset_manifest.json` | 本次生成的数据清单 |
| `sample_pack/` | 小样例包，供组员快速调试 |

## 5. ID 映射规则

新版 30k 简历 ID 类似：

```text
resume_000001_exp00_0
resume_000001_exp01_1
```

旧金银标里的简历 ID 类似：

```text
resume_000001
```

脚本会把旧标签中的 `resume_000001` 映射到对应的新简历版本，优先选择经验年限最小、ID 排序最靠前的版本。

旧金银标里的岗位 ID 类似：

```text
job_89816a4b61adce2b1da0
```

新版企业岗位 ID 类似：

```text
JOB00001
```

两者不是天然同一套 ID。为保证旧金银标可以先跑通评估，脚本会从旧金银标中抽取这些 `job_...` 岗位，生成：

```text
jobs_label_legacy.jsonl
```

并将它们合入 `jobs.jsonl`。后续如果数据集小组重新生成新版金银标，应直接使用新版 `candidate_id` 和 `job_id`，不要再依赖 legacy 映射。

## 6. 各工作流读取方式

通用读取：

```text
artifacts/dataset_iteration_05/jobs.jsonl
artifacts/dataset_iteration_05/candidate_profiles.jsonl
```

只需要企业岗位：

```text
artifacts/dataset_iteration_05/jobs_enterprise.jsonl
```

只需要公务员岗位：

```text
artifacts/dataset_iteration_05/jobs_government.jsonl
```

小规模调试：

```text
artifacts/dataset_iteration_05/sample_pack/
```

## 7. 注意事项

- 生成产物默认放在 `artifacts/`，一般不提交到 Git。
- 代码和文档提交到 Git，完整数据产物本地生成。
- 标准输出不会包含姓名、电话、邮箱等直接个人信息。
- 当前 legacy 映射是为了兼容旧金银标，不是最终方案。
- 正式评估阶段最好重新生成与 `dataset_iteration_05` 完全对齐的金标/银标。
