# LLM Labeling Guidelines

## Task

Given one resume profile and one job posting, judge how well the candidate matches the job. Return structured JSON only.

The label should reflect job-resume matching quality, not whether the job itself is good.

## Grade Definition

- `0`: irrelevant. Job family, core skills, or hard constraints clearly do not match.
- `1`: weakly relevant. Some overlap exists, but the candidate misses major required skills or the role direction is different.
- `2`: relevant. Candidate satisfies important requirements and has reasonable evidence, but still has some gaps.
- `3`: strongly relevant. Candidate closely matches job family, core skills, experience direction, and hard constraints.

## Hard Constraints

Set `hard_constraint_pass=false` when the resume clearly violates a hard requirement, for example:

- required clearance, license, or location is absent
- required seniority is far above the candidate profile
- required domain is explicit and the resume has no related evidence

If the job does not state hard constraints, use `true`.

## Evidence Rules

Each positive label (`grade` 2 or 3) must include:

- at least one `resume_evidence`
- at least one `job_evidence`
- at least one `matched_skills` item when skills are available

For negative or weak labels, include missing skills or hard-constraint reasons when possible.

## Output JSON

Return one JSON object per pair:

```json
{
  "candidate_id": "resume_001",
  "job_id": "job_001",
  "grade": 2,
  "hard_constraint_pass": true,
  "matched_skills": ["Python", "SQL"],
  "missing_required_skills": ["PyTorch"],
  "resume_evidence": ["熟悉 Python 数据分析"],
  "job_evidence": ["岗位要求 Python 和深度学习框架"],
  "confidence": 0.86,
  "label_source": "llm",
  "annotator_id": "model_name_or_human_id",
  "notes": ""
}
```

## Prompt Template

```text
你是人岗匹配标注员。请根据简历与岗位信息判断匹配等级。

等级定义：
0 = 不相关
1 = 弱相关
2 = 较相关
3 = 强相关

请重点判断：
1. 岗位族/岗位方向是否一致
2. 核心技能是否匹配
3. 经验、项目、行业背景是否有证据
4. 是否违反硬性约束
5. 缺失哪些必要技能

只输出 JSON，不要输出解释性段落。

候选人：
{candidate_snapshot}

岗位：
{job_snapshot}

输出字段：
candidate_id, job_id, grade, hard_constraint_pass, matched_skills,
missing_required_skills, resume_evidence, job_evidence, confidence,
label_source, annotator_id, notes
```

## Review Policy

LLM labels are not formal gold labels by default. Before formal evaluation:

- manually review 10%-20% of records
- prioritize low-confidence records
- prioritize boundary cases between grade 1/2 and 2/3
- check inconsistent duplicate labels
- record reviewer ID and notes

