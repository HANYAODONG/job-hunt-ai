# Frontend-Backend Gap List

Updated after merging PR #15/#16/#17.

## Current Live / Mock Status

| Area | Page / Service | Status | Notes |
| --- | --- | --- | --- |
| Fusion recommendation | `/fusion-demo`, `fusionApi.recommendJobs` | live | Calls `POST /api/v1/fusion/recommend`; keeps offline/mock modes for fallback. |
| Resume diagnosis | `/diagnosis`, `talentApi.diagnoseCandidate` | live with fallback | Intended chain: resume upload -> BM25 -> semantic rerank -> KG gap -> fusion rank. Falls back to legacy recommendations if the full chain fails. |
| BM25 retrieval | `intelligenceApi.searchBm25` | live | Calls `/api/v1/bm25/search`. |
| Semantic rerank | `intelligenceApi.rerankSemantic` | live | Calls `/api/v1/semantic/rerank`. |
| KG gap analysis | `intelligenceApi.analyzeKnowledgeGraphGap` | live | Calls `/api/v1/kg/analyze`; requires job_id/candidate_id alignment. |
| Market CSV ingestion | `talentApi.importMarketCsv` | live | Calls CSV ingestion API. |
| Market runtime stats | `talentApi.getMarketRuntimeStatus` | partial-live | Uses backend stats, but trend candidates are still mock. |
| Graph visualization | `/graph`, `getCapabilityGraph` | mock-only | Needs real nodes/edges graph API. |
| Learning plan | `/learning`, `getLearningPlan` | mock-only | Needs learning-path generation API. |
| Recruitment jobs | `/recruitment`, `getRecruitmentJobs` | mock-only | Needs enterprise job list/detail/update APIs. |
| Candidate pipeline | `/candidates`, `getJobCandidates` | mock-only | Needs job-to-candidate matching and candidate-stage APIs. |
| Dashboard overview | `/`, `getTalentOverview` | mock-only | Needs aggregate dashboard API if required for final demo. |
| Governance / evaluation | `/governance`, `/evaluation` | mock-only | Low priority unless final frontend keeps these pages. |

## Page-Level Gaps

### `/fusion-demo`

Already connected to `POST /api/v1/fusion/recommend`.

Remaining work:

- Run browser-level verification after Docker/Node environment is available.
- Confirm result cards show `final_score`, `score_breakdown`, matched skills, missing skills, and explanation.

### `/diagnosis`

Partially connected to the real backend chain.

Remaining work:

- Verify actual resume upload flow on the new machine.
- Confirm BM25 job IDs, KG job IDs, and fusion job IDs are aligned.
- Improve empty/error states when one backend stage is unavailable.

### `/graph`

Still mock-only.

Needed backend output:

```json
{
  "nodes": [],
  "edges": [],
  "snapshot_id": "2026",
  "metadata": {}
}
```

Each node should include id, label, type, weight/count, and optional year. Each edge should include source, target, relation, and weight.

### `/learning`

Still mock-only.

Needed backend output:

```json
{
  "target_role": "...",
  "missing_skills": [],
  "stages": [],
  "resources": []
}
```

This can be generated from diagnosis gaps plus optional LLM explanation later.

### `/recruitment`

Still mock-only.

Needed backend output:

- Job list
- Job detail
- Job status update
- Job skill requirements
- Job source and update timestamp

The new JD update module from PR #16 may support part of this, but the page service is not wired to it yet.

### `/candidates`

Still mock-only.

Needed backend output:

- Candidate list by job ID
- Candidate match score
- Matched skills and missing skills
- Explanation or screening reason
- Candidate stage update

### `/signals`

Partial-live.

Already can use backend stats/CSV ingestion, but discovery candidates and market-change candidates still come from mock data.

The new JD update module may become the backend source for market signals after its API contract is mapped to the frontend.

## Legacy Pages

The old pages remain available:

- `/search`
- `/recommendations`
- `/personalized-recommendations`
- `/upload-resume`
- `/job/:jobId`

They still use older search/recommendation APIs. Do not migrate all of them at once. Prefer finishing the new workbench pages first.

## Priority

1. Verify `/fusion-demo` with real backend.
2. Verify `/diagnosis` full chain with uploaded resume.
3. Wire `/signals` to the new JD update module where possible.
4. Add real graph API for `/graph`.
5. Add recruitment/candidate APIs for `/recruitment` and `/candidates`.
6. Add learning-path API for `/learning`.

---

# 第五轮更新（2026-08-19）— 纪雨涵

> 分工依据：`F:\揭榜挂帅\分工5.md`。本轮主线：前端页面逐个检查 → 能接真实接口的先接 → 缺后端的写清缺口。

## 数据就绪（关键）

- `artifacts/dataset_iteration_05/sample_pack/` 就绪：5 个候选人（`resume_000001_exp00_0` 等，大模型算法工程师方向）+ 岗位 + 标注对。
- **`POST /api/v1/fusion/recommend` 的 `mode=sample` 可在无 ES / 无语义模型 / 无 Neo4j 的情况下跑通全链路**（简化 BM25 + jaccard 语义 + 技能/图谱计算）。
- `/fusion/recommend` 返回 `results[].meta` 含 `title / company / standard_job / job_family / location / salary`，前端可直接展示岗位信息。
- 返回字段契约：`job_id, final_score, rank, score_breakdown{bm25,semantic,skill_coverage,job_family,graph}, explanation{matched_skills,missing_skills,reason}, evidence_paths, meta`。

## 各页面第五轮状态

| 页面 | 状态 | 说明 | 负责人 |
| --- | --- | --- | --- |
| `/fusion-demo` | ✅ 已接 | `recommendJobs()` → `/fusion/recommend`，四种模式齐全 | 纪雨涵 |
| `/diagnosis` | ✅ 已接 | 全链路 live（上传→BM25→Semantic→KG→Fusion），降级 fallback | 叶骑瑞/纪雨涵 |
| `/recommendations` | 🔄 本轮已接 | 改接 `/fusion/recommend`（sample），复用 FusionScoreCard | 纪雨涵 |
| `/search` | ⚠️ 旧接口 | 仍走旧 `/jobs/search`（英文市场）；legacy 页面暂不整体迁移 | 纪雨涵 |
| `/signals` | ⚠️ partial-live | 基础统计 real，趋势候选 mock；JD 更新模块可成为数据源 | 李佳蔓/魏昊朗 |
| `/graph` | ❌ mock-only | 需 nodes/edges 图谱接口（分工5 已定义最小结构） | 魏昊朗 |
| `/learning` | ❌ mock-only | 需学习路径接口（分工5 已定义最小输出） | 叶骑瑞 |
| `/recruitment` | ❌ mock-only | 部分可复用 `/jobs/*` CRUD | 甘可欣 |
| `/candidates` | ❌ mock-only | `POST /bm25/candidates` 可复用 | 甘可欣 |

## 本轮对接说明

- `/recommendations` 数据流：上传简历 → `uploadResume` → 构建 query_text → `recommendJobs({candidateId, queryText, topK, mode:'sample'})` → `FusionScoreCard` 渲染。
- 页面新增"使用示例候选人"入口（`resume_000001_exp00_0`），可完整展示 matched/missing skills。
- 注意：**任意新上传简历的 candidate_id 不在 sample_pack 时，`_find_candidate` 返回空 → matched/missing skills 可能为空**（分数/排序仍正常）。建议后续后端支持直接传入简历技能列表，或前端预匹配 sample 候选人。

## 遗留 / 协调项

1. **PR #16 `.env` 与 Settings 不同步**：本地 `.env` 含 `DOCKER_USERNAME` / `FRONTEND_PORT` 未定义字段，`python` 直接跑后端报 `extra_forbidden`。Docker 部署不受影响。建议修 `config.py`（`extra="ignore"`）或清理 `.env`。已协调韩耀栋。
2. **`talentApi.js` 被英文化**（PR #15/#17）：`fitLabels`、gap priority、`'岗位库'`→`'Job'` 等改为英文，`/diagnosis` 展示语言受影响。待确认是否为预期。
3. **BM25/KG/fusion job_id 对齐**（组长 gap-list 已提）：sample 链路内部自洽；与 ES/Neo4j 数据源对齐待魏昊朗（KG）与甘可欣（BM25 索引）。

## 网页测试计划

- 后端：Docker `docker compose up -d --build`，四服务 healthy。
- 前端：`http://localhost:18080`。
- 测试页：`/fusion-demo`（统一推荐模式）、`/recommendations`（上传简历 + 示例候选人）、`/diagnosis`（上传 PDF）。
- 记录文件：`F:\揭榜挂帅\网页测试记录_第五轮.md`（进行中）。
