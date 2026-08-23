# Job Update 云盘数据包清单

## 1. 目的

`job_update` 模块包含岗位动态更新、岗位画像、技能频率、技能生命周期、技能迁移、岗位趋势分析等功能。该模块需要一批 CSV 和 SQLite 数据库文件作为运行基础。

这些文件体积较大，不适合直接提交到 Git 仓库。后续统一通过夸克网盘分发，仓库只保留代码、README、接口和小规模 sample。

## 2. 推荐云盘压缩包名称

```text
job_update_runtime_data_2026_xx.zip
```

建议压缩包解压后直接得到下面这个目录结构：

```text
backend-src/
  job_update/
    company_job_update/
      data/
        versions/
          company_large_v2/
            ...
    government_job_update/
      data/
        base/
          ...
      government_jobs_2024_2026_tech_final.csv
```

这样组员下载后可以直接把 `backend-src` 覆盖/合并到项目根目录，不需要手动一个个放文件。

## 3. 公司岗位数据：必需

代码默认读取：

```text
backend-src/job_update/company_job_update/data/versions/company_large_v2/
```

如果后续使用其他版本名，需要在环境变量中设置：

```text
COMPANY_DATA_VERSION=<version_name>
```

默认版本 `company_large_v2` 下建议包含：

```text
backend-src/job_update/company_job_update/data/versions/company_large_v2/
  job_current_profile_system.csv
  job_profile_diff.csv
  job_profile_snapshots.csv
  job_skill_monthly_frequency.csv
  job_update.db
  job_update_event_stream.csv
  skill_job_monthly_spread.csv
  skill_lifecycle.csv
  skill_migration.csv
  skill_pool.csv
  standard_job_title_dictionary.csv
  version_manifest.json
```

这些文件用于：

- 公司岗位动态更新。
- 公司岗位画像展示。
- 公司岗位技能趋势统计。
- 公司岗位技能生命周期分析。
- 公司岗位技能迁移分析。
- `/signals`、`/recruitment` 等页面后续真实数据支撑。

## 4. 政府岗位数据：必需

代码默认读取：

```text
backend-src/job_update/government_job_update/data/base/
```

建议包含：

```text
backend-src/job_update/government_job_update/data/base/
  government_initial_job_assignment.csv
  government_job_current_profile_system.csv
  government_job_event_stream.csv
  government_job_event_stream_raw.csv
  government_job_postings_normalized.csv
  government_job_profile_diff.csv
  government_job_profile_snapshots.csv
  government_job_skill_monthly_frequency.csv
  government_job_update.db
  government_skill_job_monthly_spread.csv
  government_skill_lifecycle.csv
  government_skill_migration.csv
  government_skill_pool.csv
  standard_job_title_dictionary.csv
```

另外政府岗位源文件也需要保留：

```text
backend-src/job_update/government_job_update/government_jobs_2024_2026_tech_final.csv
```

这些文件用于：

- 政府技术岗位年度事件流。
- 政府岗位技能频率统计。
- 政府岗位技能生命周期分析。
- 政府岗位画像。
- 动态图谱和岗位趋势分析。

## 5. 工作流 1 标准数据集：建议一并上传

这部分不是 `job_update` 模块本身的数据库，但很多工作流会用到，建议也放到同一个网盘目录中，方便组员统一下载。

本地路径：

```text
artifacts/dataset_iteration_05/
```

建议包含：

```text
artifacts/dataset_iteration_05/
  candidate_profiles.jsonl
  jobs.jsonl
  jobs_enterprise.jsonl
  jobs_government.jsonl
  jobs_label_legacy.jsonl
  label_pairs_gold.jsonl
  label_pairs_silver.jsonl
  data_quality_report.json
  dataset_manifest.json
  sample_pack/
    candidate_profiles_sample.jsonl
    jobs_sample.jsonl
    label_pairs_gold_sample.jsonl
    label_pairs_silver_sample.jsonl
    sample_manifest.json
```

用途：

- BM25 索引构建。
- BGE/text2vec 语义向量生成。
- 融合排序评估。
- 金标/银标评估。
- sample 小规模联调。

## 6. 原始输入数据：建议单独放一个 raw_data 目录

如果数据小组后续还会继续更新原始 CSV，建议云盘里单独建：

```text
raw_data/
```

目前提到过的原始文件包括：

```text
government_jobs_2024_2026_tech_final.csv
government_jobs_2026_tech_filtered.csv
synthetic_detailed_resumes_experience_30k.csv
synthetic_detailed_resumes.csv
```

说明：

- `government_jobs_2024_2026_tech_final.csv` 是当前更推荐使用的政府岗位源数据，因为包含年份字段。
- `synthetic_detailed_resumes_experience_30k.csv` 是当前更推荐使用的扩展简历数据。
- 老版本文件可以保留，但应标注“legacy”。

## 7. 不建议上传到 Git，但可以上传到网盘的内容

```text
*.db
大体积 CSV
完整 artifacts 产物
模型 embedding 向量
全量索引中间结果
```

这些文件可以放网盘，因为它们对运行或复现实验有价值；但不建议直接放进 Git 仓库。

## 8. 下载后放置方式

组员下载压缩包后，在项目根目录执行解压或手动覆盖，使路径最终变成：

```text
job-hunt-ai/
  backend-src/
    job_update/
      company_job_update/
        data/
          versions/
            company_large_v2/
      government_job_update/
        data/
          base/
        government_jobs_2024_2026_tech_final.csv
  artifacts/
    dataset_iteration_05/
```

检查关键文件是否存在：

```powershell
Test-Path .\backend-src\job_update\company_job_update\data\versions\company_large_v2\job_update.db
Test-Path .\backend-src\job_update\government_job_update\data\base\government_job_update.db
Test-Path .\backend-src\job_update\government_job_update\government_jobs_2024_2026_tech_final.csv
Test-Path .\artifacts\dataset_iteration_05\jobs.jsonl
Test-Path .\artifacts\dataset_iteration_05\candidate_profiles.jsonl
```

如果都返回 `True`，说明基础数据包放置正确。

## 9. 给组员的说明

可以直接发：

```text
这次 job_update/data 里的文件不是普通中间产物，其中一部分是运行必需的基础数据库和分析表。为了避免 Git 仓库过大，我们不把完整 CSV/DB 放进仓库，统一放到夸克网盘。

大家下载数据包后，把里面的 backend-src 和 artifacts 合并到项目根目录即可。重点检查：

1. backend-src/job_update/company_job_update/data/versions/company_large_v2/job_update.db
2. backend-src/job_update/government_job_update/data/base/government_job_update.db
3. backend-src/job_update/government_job_update/government_jobs_2024_2026_tech_final.csv
4. artifacts/dataset_iteration_05/jobs.jsonl
5. artifacts/dataset_iteration_05/candidate_profiles.jsonl

这些文件不提交 Git，只用于本地运行和联调。
```
