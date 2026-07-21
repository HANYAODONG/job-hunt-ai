# 数据基座字段契约

本文档对应工作流 1：数据基座与标签评估，定义后续 BM25、Embedding、知识图谱、融合排序等工作流共同使用的数据格式。

生成脚本：

```powershell
python .\scripts\dataset_adapter.py
```

默认输出目录：

```text
artifacts/dataset_iteration_05/
```

注意：`artifacts/` 已加入 `.gitignore`，输出文件用于本地开发和组内传递，不默认提交到 Git。

当前 iteration 05 默认读取：

```text
dataset/incoming/job_bigcompany_final.csv
dataset/incoming/standard_job_title_dictionary.csv
dataset/incoming/synthetic_detailed_resumes.csv
```

金标和银标文件为可选输入；缺失时仍生成岗位、简历、样例包和质量报告，但不能进行正式排序评估。

## 1. 标准岗位文件

文件：

```text
artifacts/dataset_iteration_05/jobs.jsonl
```

一行一个岗位对象。

必备字段：

```json
{
  "job_id": "job_001",
  "title": "机器学习工程师",
  "description": "负责推荐算法、模型训练和数据分析。",
  "skills": ["Python", "Machine Learning", "SQL"],
  "job_family": "AI算法类",
  "company": "示例公司",
  "location": "深圳",
  "source": "dataset_group_silver_jsonl"
}
```

字段说明：

| 字段 | 类型 | 说明 | 下游使用方 |
|---|---|---|---|
| `job_id` | string | 岗位唯一 ID | 全部工作流 |
| `title` | string | 岗位标题 | BM25、Embedding、前端展示 |
| `description` | string | 岗位 JD 文本 | BM25、Embedding、技能抽取 |
| `skills` | string[] | 已归一或候选技能列表 | 图谱、融合排序 |
| `job_family` | string | 岗位族/岗位大类 | 图谱、融合排序 |
| `company` | string | 公司名称 | 前端展示、检索筛选 |
| `location` | string | 地点 | 检索筛选、解释 |
| `source` | string | 数据来源 | 数据追踪 |

兼容字段：

- `id`：与 `job_id` 相同，兼容旧代码。
- `required_skills`：与 `skills` 基本一致，兼容原 demo。
- `company_name`：与 `company` 基本一致。
- `location_text`：与 `location` 基本一致。
- `search_metadata`：保留数据来源、银标方法、岗位族投票等附加信息。

大公司岗位扩展字段：

- `standard_job`、`standard_category`：标准岗位名称和词典类别。
- `responsibilities`、`requirements`、`detailed`：用于 BM25 分字段加权的岗位文本。
- `traditional_skills`、`new_skills`、`domain_context`：技能和行业上下文数组。
- `publish_time`、`publish_time_raw`：统一日期和原始时间值，异常占位日期转为空。
- `source_type`、`content_hash`：来源类型和内容版本追踪。

当前 `job_family` 暂时沿用 `standard_job`；正式评测前需要补充到简历 10 类 `target_job_family` 的团队统一映射。

## 2. 标准简历文件

文件：

```text
artifacts/dataset_iteration_05/candidate_profiles.jsonl
```

一行一个简历/候选人对象。

必备字段：

```json
{
  "candidate_id": "resume_001",
  "summary": "熟悉 Python、SQL，有数据分析项目经验。",
  "skills": ["Python", "SQL", "Data Analysis"],
  "target_job_family": "AI算法类",
  "preferred_location": "深圳"
}
```

字段说明：

| 字段 | 类型 | 说明 | 下游使用方 |
|---|---|---|---|
| `candidate_id` | string | 候选人/简历唯一 ID | 全部工作流 |
| `summary` | string | 简历主体文本 | BM25、Embedding |
| `skills` | string[] | 简历技能列表 | 图谱、融合排序 |
| `target_job_family` | string | 目标岗位族 | 图谱、融合排序 |
| `preferred_location` | string | 期望地点，若原数据没有则为空 | 搜索筛选、解释 |

兼容字段：

- `resume_id`：与 `candidate_id` 相同。
- `source_resume_id`：原始简历 ID。
- `profile_text`：与 `summary` 相同。
- `skills_normalized`：与 `skills` 基本一致。
- `education`、`experience`、`projects`：保留结构化简历信息。

隐私约束：

- 标准输出不包含姓名、电话、邮箱等 PII 字段。
- 如后续接真实简历，仍需在进入标准文件前脱敏。

## 3. 标签文件

金标文件：

```text
artifacts/dataset_iteration_05/label_pairs_gold.jsonl
```

银标文件：

```text
artifacts/dataset_iteration_05/label_pairs_silver.jsonl
```

统一字段：

```json
{
  "candidate_id": "resume_001",
  "resume_id": "resume_001",
  "job_id": "job_001",
  "pair_key": "resume_001::job_001",
  "label_source": "gold",
  "grade": 3
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `candidate_id` | string | 简历 ID，推荐下游统一使用这个字段 |
| `resume_id` | string | 与 `candidate_id` 相同，兼容原数据 |
| `job_id` | string | 岗位 ID |
| `pair_key` | string | 简历-岗位组合键 |
| `label_source` | string | `gold` 或 `silver` |
| `grade` | int | 匹配等级 |

等级约定：

| grade | 含义 |
|---|---|
| 0 | 不相关或明显不匹配 |
| 1 | 弱相关 |
| 2 | 较相关，可作为正样本 |
| 3 | 强相关 |

默认评估时：

```text
positive_grade >= 2
```

即 `grade` 为 2 或 3 的样本视为正样本。

银标额外字段：

| 字段 | 说明 |
|---|---|
| `score` | 银标综合分 |
| `bm25_rank` | BM25 排名 |
| `bm25_score` | BM25 得分 |
| `semantic_rank` | 语义排名 |
| `semantic_score` | 语义相似度 |
| `family_match` | 岗位族匹配 |
| `skill_coverage` | 技能覆盖率 |
| `matched_skills` | 匹配技能 |

金标额外字段：

| 字段 | 说明 |
|---|---|
| `hard_constraint_pass` | 硬约束是否通过 |
| `matched_skills` | 匹配技能 |
| `missing_required_skills` | 缺失必需技能 |
| `missing_optional_skills` | 缺失可选技能 |
| `transferable_skills` | 可迁移技能 |
| `resume_evidence` | 简历证据 |
| `job_evidence` | 岗位证据 |
| `annotator_id` | 标注者 |
| `notes` | 标注备注 |

## 4. 固定样例包

文件夹：

```text
artifacts/dataset_iteration_05/sample_pack/
```

包含：

```text
candidate_profiles_sample.jsonl
jobs_sample.jsonl
label_pairs_gold_sample.jsonl
label_pairs_silver_sample.jsonl
sample_manifest.json
```

用途：

- 其他同学在完整数据接入前可以先用样例开发。
- BM25 同学可以导入 `jobs_sample.jsonl`。
- Embedding 同学可以对 `jobs_sample.jsonl` 和 `candidate_profiles_sample.jsonl` 生成向量。
- 图谱同学可以用样例技能构建小图。
- 融合排序同学可以用样例标签和 mock 分数调试。

## 5. 质量报告

文件：

```text
artifacts/dataset_iteration_05/data_quality_report.json
```

包含：

- 各文件记录数。
- 关键字段缺失数量。
- 标签分布。
- 金标/银标对简历和岗位的引用检查。

如果质量报告中出现大量 `missing_job_refs` 或 `missing_candidate_refs`，说明标签文件中的 ID 与标准岗位/简历文件没有对齐，需要优先排查。

## 6. 评估脚本

### 6.1 通用 JSON/JSONL 排序评估

脚本：

```text
scripts/evaluate_candidate_rankings.py
```

适用场景：

- BM25 工作流输出候选集后评估。
- Embedding 工作流输出语义重排后评估。
- 融合排序工作流输出最终排序后评估。
- 任意同学输出 JSON/JSONL 排序结果后评估。

支持输入：

扁平 JSONL：

```json
{"query_id":"resume_001","job_id":"job_001","final_score":0.79}
```

Batch JSON：

```json
{
  "query_id": "resume_001",
  "results": [
    {"job_id": "job_001", "final_score": 0.79}
  ]
}
```

Batch JSONL：

```json
{"query_id":"resume_001","candidates":[{"job_id":"job_001","bm25_score":12.34,"bm25_rank":1}]}
```

示例命令：

```powershell
python .\scripts\evaluate_candidate_rankings.py `
  --ranking ".\artifacts\bm25\bm25_top200.jsonl" `
  --labels ".\artifacts\dataset_iteration_05\label_pairs_gold.jsonl" `
  --score-field bm25_score `
  --rank-field bm25_rank `
  --positive-grade 2 `
  --ks 10,100,200 `
  --output ".\artifacts\dataset_iteration_05\bm25_baseline_eval_report.json"
```

当前 iteration 05 的金标文件为空；收到工作流 1 的真实标签后才能运行并解释这份报告。

## 7. 下游工作流对接建议

### BM25 工作流

输入：

```text
jobs.jsonl
candidate_profiles.jsonl 或 query 文本
```

输出候选集：

```json
{
  "query_id": "resume_001",
  "candidates": [
    {
      "job_id": "job_001",
      "bm25_score": 12.34,
      "bm25_rank": 1
    }
  ]
}
```

### Embedding 工作流

输入：

```text
jobs.jsonl
candidate_profiles.jsonl
BM25 candidates 或 mock candidates
```

输出：

```json
{
  "query_id": "resume_001",
  "candidates": [
    {
      "job_id": "job_001",
      "semantic_score": 0.82,
      "semantic_rank": 1
    }
  ]
}
```

### 知识图谱工作流

输入：

```text
jobs.jsonl
candidate_profiles.jsonl
```

输出：

```json
{
  "query_id": "resume_001",
  "job_id": "job_001",
  "skill_coverage": 0.67,
  "job_family_match": 1.0,
  "graph_relatedness": 0.72,
  "missing_skills": ["Machine Learning"],
  "evidence_paths": []
}
```

### 融合排序工作流

输入：

```json
{
  "query_id": "resume_001",
  "job_id": "job_001",
  "bm25_score": 0.76,
  "semantic_score": 0.82,
  "skill_coverage": 0.67,
  "job_family_match": 1.0,
  "graph_relatedness": 0.72,
  "missing_skills": ["Machine Learning"],
  "evidence_paths": []
}
```

输出：

```json
{
  "query_id": "resume_001",
  "job_id": "job_001",
  "final_score": 0.79,
  "rank": 1,
  "score_breakdown": {
    "bm25": 0.76,
    "semantic": 0.82,
    "skill_coverage": 0.67,
    "job_family": 1.0,
    "graph": 0.72
  },
  "explanation": "该岗位与简历在 Python、SQL 上匹配度较高，但仍缺少 Machine Learning 相关能力。"
}
```
