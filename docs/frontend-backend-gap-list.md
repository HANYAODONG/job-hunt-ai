# Frontend-Backend Gap List

Updated after merging PR #15/#16/#17.

## Current Live / Mock Status

| Area | Page / Service | Status | Notes |
| --- | --- | --- | --- |
| Fusion recommendation | `/fusion-demo`, `fusionApi.recommendJobs` | live | Calls `POST /api/v1/fusion/recommend`; keeps offline/mock modes for fallback. |
| Resume diagnosis | `/diagnosis`, `talentApi.diagnoseCandidate` | live with fallback | Intended chain: resume upload -> BM25 -> semantic rerank -> KG gap -> fusion rank. Falls back to legacy recommendations if the full chain fails. Also exposes a stable backend contract at `POST /api/v1/diagnosis/analyze`. |
| BM25 retrieval | `intelligenceApi.searchBm25` | live | Calls `/api/v1/bm25/search`. |
| Semantic rerank | `intelligenceApi.rerankSemantic` | live | Calls `/api/v1/semantic/rerank`. |
| KG gap analysis | `intelligenceApi.analyzeKnowledgeGraphGap` | live | Calls `/api/v1/kg/analyze`; requires job_id/candidate_id alignment. |
| Market CSV ingestion | `talentApi.importMarketCsv` | live | Calls CSV ingestion API. |
| Market runtime stats | `talentApi.getMarketRuntimeStatus` | partial-live | Uses backend stats, but trend candidates are still mock. |
| Graph visualization | `/graph`, `getCapabilityGraph` | mock-only | Needs real nodes/edges graph API. |
| Learning plan | `/learning`, `getLearningPlan` | live with fallback | Calls `POST /api/v1/learning/plan` from diagnosis gaps; falls back to mock when backend unavailable. |
| Recruitment jobs | `/recruitment`, `getRecruitmentJobs` | live with fallback | Reads 12,675 enterprise jobs and supports runtime detail/status edits through `/api/v1/talent/jobs`. |
| Candidate pipeline | `/candidates`, `getJobCandidates` | live with fallback | Reads 30,200 candidate profiles, returns explainable baseline scores, and persists candidate stages through `/api/v1/talent/jobs/{job_id}/candidates`. |
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

Connected to `POST /api/v1/learning/plan` with mock fallback.

Backend output (minimal contract):

```json
{
  "target_role": "...",
  "missing_skills": [{"skill": "...", "priority": "high", "reason": "..."}],
  "stages": [
    {
      "id": "stage-1",
      "skill": "...",
      "priority": "high",
      "learning_stage": "阶段 1",
      "title": "...",
      "suggestion": "...",
      "resources": ["..."]
    }
  ],
  "resources": []
}
```

Generated from diagnosis gaps (`careerTarget` in localStorage) via a deterministic
skill-suggestion library; no LLM required. The `/diagnosis` page already writes
`careerTarget` before navigating to `/learning`, so the two pages are chained.

### `/recruitment`

Connected to the artifact-backed talent API with mock fallback.

- Job list, detail, skill requirements, source, and update timestamp come from the standardized enterprise dataset.
- Runtime edits and status updates are supported, but are not written back to the source dataset.
- The JD update module remains available independently for incremental update workflows.

### `/candidates`

Connected to the artifact-backed talent API with mock fallback.

- Candidate list, matched/missing skills, screening reason, and stage update are available.
- Current ranking is an explainable baseline: skill overlap 65%, role-family/category consistency 25%, and experience 10%.
- Replace the baseline with BM25, BGE-M3, Neo4j, and Fusion results after their IDs and score contracts are aligned.

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
5. Replace the candidate baseline with aligned BM25, BGE-M3, Neo4j, and Fusion results.
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
| `/diagnosis` | ✅ 已接 | 全链路 live（上传→BM25→Semantic→KG→Fusion），降级 fallback；新增 `POST /api/v1/diagnosis/analyze` 稳定字段契约 | 叶骑瑞/纪雨涵 |
| `/recommendations` | 🔄 本轮已接 | 改接 `/fusion/recommend`（sample），复用 FusionScoreCard | 纪雨涵 |
| `/search` | ⚠️ 旧接口 | 仍走旧 `/jobs/search`（英文市场）；legacy 页面暂不整体迁移 | 纪雨涵 |
| `/signals` | ⚠️ partial-live | 基础统计 real，趋势候选 mock；JD 更新模块可成为数据源 | 李佳蔓/魏昊朗 |
| `/graph` | ❌ mock-only | 需 nodes/edges 图谱接口（分工5 已定义最小结构） | 魏昊朗 |
| `/learning` | ✅ 已接 | 接 `/learning/plan`，由诊断缺口生成，mock 兜底 | 叶骑瑞 |
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

---

# 第六轮更新（2026-08-26）— 纪雨涵

> 依据：`F:\揭榜挂帅\分工6-任务书验收收尾.md`。环境全新重建（main `7b0ba1d`，Docker `up --build`，四服务 healthy），三个数据压缩包已解压。
> 完整测试报告：`F:\揭榜挂帅\网页测试记录_第六轮_任务书验收.md`。

## 各页面第六轮实测状态

| 页面 | 状态 | 真实接口（实测） | 说明 |
| --- | --- | --- | --- |
| `/fusion-demo` | ✅ live | `GET /fusion/weights/layered`、`POST /fusion/recommend` | 输入查询后 10 条结果 + 解释 + 缺失技能（sample 链路真实后端计算） |
| `/recommendations` | ✅ live | `POST /fusion/recommend` | 示例候选人入口可用 |
| `/diagnosis` | ⚠️ live 但**完整链路降级** | `POST /jobs/upload-resume`、`POST /bm25/search`、`POST /semantic/rerank`、`POST /kg/analyze` | 上传真实 PDF 后全接口 200，但 **BM25 与 KG job_id 不对齐**，KG 差距分析无法完成 → 降级到旧推荐接口（**P1**） |
| `/graph` | ✅ live（数据） / ❌ 年份未接 | `GET /api/v1/graph` | 真实 tree（12675 岗位、9 domain、69 family）。**年份切换未对接**：前端不传 year、后端无 year 参数、growth 硬编码 +0%（**P1，组长第一优先**）。`stackDomainMap` 用 mock id → 技术栈导航失效（智能终端映射待魏昊朗确认） |
| `/signals` | ✅ live（企业模式） | `GET /jd-update/analytics/jobs`、`/overview`、`/reviews`、`/optimization/profile`、`/analytics/job-trend`、`/lifecycle`、`/skill-migration` | RoleEvolutionCenter（PR #21），真实数据（大模型应用工程师 v1.2、证据 27） |
| `/recruitment` | ✅ live（企业模式） | `GET /talent/recruitment/jobs` | 12675 岗位，显示 50 条，JOB00001 后端开发工程师岗 |
| `/candidates` | ✅ live（企业模式） | `GET /talent/recruitment/jobs`、`GET .../jobs/{job_id}/candidates` | 30200 候选池、三路并集 27420；**无参自动选 JOB00001**，完整加载 |
| `/learning` | ❌ mock | - | 缺口（叶骑瑞） |
| `/search` | ⚠️ 旧接口 | 旧 `/jobs/search` | 英文市场 legacy，暂不迁移 |
| `/upload-resume` | ✅ 入口 | - | 上传流程已并入 /diagnosis |

## 新增关键问题（第六轮实测确认）

### P1-1 诊断完整链路降级：BM25 与 KG 的 job_id 不对齐
- 现象：`/diagnosis` 上传简历后显示"完整智能匹配流水线已降级：BM25 job ids are not aligned with knowledge graph job ids"，KG 差距分析无法完成，结果退回旧推荐接口。
- 归属：魏昊朗（KG 数据源）∪ 甘可欣（BM25 索引）。**可复现**：/diagnosis 上传任意简历。

### P1-2 动态图谱年份切换未对接（组长点名第一优先）
- 前端 `getCapabilityGraph()` 不传 year；后端 `/api/v1/graph` 无 year 参数；growth 全部 `+0%`。数据存在（job_update.db 版本化、政府 CSV 2024_2026），缺接线。
- 归属：魏昊朗（后端按年快照 + 前端传参）。**可复现**：/graph 切年份数据不变。

### P1-3 企业端岗位详情 404
- `/jobs/{job_id}` 从 **ES** 查，企业岗位（JOB00001）在企业数据集不在 ES → `/job/JOB00001` 404。
- 归属：接口数据源需统一（详情接口改用 talent_data_service 或把企业岗位索引进 ES）——需韩耀栋协调。**可复现**：/recruitment 点任一岗位。

### P2 /graph 技术栈导航失效（映射待确认）
- `stackDomainMap` 用 mock 时代 id（ai/data/intelligent-system），真实 domain id 为 `domain_XXX`。大模型→domain_大模型、数据智能→domain_数据 已确定；智能终端→哪一岗位类待魏昊朗确认。

## 协作 / 环境备注

- **角色门控**（设计特性）：默认求职者模式，`/recruitment` `/candidates` `/signals` 被重定向到 `/diagnosis`；右上角切"企业"后跳 `/recruitment`。
- **数据就绪**：`artifacts/dataset_iteration_05/`（345MB）、`company_large_v2/job_update.db`（178MB）、`gov data/base/government_job_update.db` + `government_jobs_2024_2026_tech_final.csv` 已解压（占位 manifest 已删）。
- **测试脚本**：`F:\揭榜挂帅\_puppeteer_test\test_docker.js`（12 页）、`test_role.js`（企业模式）、`diag_route.js`。截图：`_puppeteer_test/phase6/`。
