# 前端接口缺口清单（v2 — 组长新前端合并后）

> 第四阶段 P0 交付物 — 纪雨涵整理  
> 更新日期：2026-08-06  
> 基于上游 `fa9f6c5` 合并后的最新代码

---

## 0. 系统概况

### 端口与代理

| 项目 | 地址 |
|------|------|
| 前端页面 | `http://localhost:18080` |
| 后端 API | `http://localhost:18088` |
| Swagger | `http://localhost:18088/docs` |
| ES | `http://localhost:9200` |

**API_BASE_URL 已修复：** `fusionApi.js` 和 `intelligenceApi.js` 已改为相对路径 `/api/v1`（依赖 `setupProxy.js` 代理到 `localhost:8000`）。但旧 `api.js` 仍默认 `http://localhost:8000/api/v1`，Docker 环境中需确认 8000→18088 映射。

---

## 1. 全局 API 能力矩阵（来自 `talentApi.js` 的 `TALENT_API_CAPABILITIES`）

| 能力 | 状态 | 后端接口 | 说明 |
|------|------|----------|------|
| **resumeDiagnosis** | ✅ live | 全链路 | 简历上传→BM25→Semantic→KG→Fusion |
| **bm25Retrieval** | ✅ live | `POST /bm25/search` | ES 中文 BM25 |
| **semanticReranking** | ✅ live | `POST /semantic/rerank` | text2vec 语义重排 |
| **knowledgeGraphGap** | ✅ live | `POST /kg/analyze` | Neo4j 技能差距分析 |
| **fusionRanking** | ✅ live | `POST /fusion/rank` | 分层融合排序 |
| **marketDataIngestion** | ✅ live | `POST /csv/ingest-csv` | CSV 市场数据导入 |
| **marketSignals** | ⚠️ partial-live | `GET /ingestion/stats` + `GET /bm25/stats` | 基础统计有，趋势数据缺 |
| **capabilityGraph** | ❌ mock-only | 无 | 岗位能力图谱可视化 |
| **learningPlan** | ❌ mock-only | 无 | 学习路径生成 |
| **recruitment** | ❌ mock-only | 无 | 企业端岗位管理 |
| **candidatePipeline** | ❌ mock-only | 无 | 企业端候选人流程 |
| **governance** | ❌ mock-only | 无 | 数据治理面板 |
| **evaluation** | ❌ mock-only | 无 | 模型评估报告 |

---

## 2. 逐页面分析（15 个路由）

### 2.1 `/diagnosis` — 人岗诊断页 ⭐

**负责：叶骑瑞（分工4.md）/ 纪雨涵（接口对接）**

**状态：核心链路已打通！**

```
diagnoseCandidate() 流程：
  uploadResume → searchBm25 → rerankSemantic → analyzeKG → rankJobs
      ✅             ✅            ✅              ✅          ✅
```

- 全链路 5 个后端接口全部 live
- 降级策略：全链路失败时 fallback 到旧 `/jobs/recommendations`
- Mock 开关：`REACT_APP_USE_RESUME_MOCK=true` 时用 Mock 数据

**缺口：**
1. **[P2]** 当前默认使用硬编码文件名 `'陈同学-前端与AI项目简历.pdf'` 触发诊断（第56行），用户实际上传功能需验证
2. **[P3]** `runFullDiagnosisPipeline` 中 BM25 size 硬编码为 8，不能调整
3. **[P3]** 诊断结果中的 `gaps` 展示的是技能缺口+通用缺口混合，通用缺口（Agent 工作流/模型评测/可观测性）是前端硬编码的

### 2.2 `/fusion-demo` — 融合排序演示页

**负责：纪雨涵** | 优先级：P1

**更新：已对接统一推荐接口！**

新增第四种模式（隐式）：`recommendJobs()` 调用 `POST /fusion/recommend`。
页面仍然保留三种显式模式：BM25 真实检索 / 离线融合结果 / Demo 演示。

**接口状态（全部 ✅）：**

| 接口 | 后端 | 前端 |
|------|------|------|
| `POST /fusion/recommend` | ✅ `4456264` | ✅ `recommendJobs()` |
| `POST /fusion/rank-from-query` | ✅ | ✅ |
| `POST /fusion/mock-rank` | ✅ | ✅ |
| `GET /fusion/load-results` | ✅ | ✅ |
| `GET/PUT /fusion/weights/layered` | ✅ | ✅ |

**缺口：**
1. **[P1]** ✅ `/fusion/recommend` 已是显式模式 — FusionDemoPage.js 第 343 行 Segmented 组件包含"统一推荐接口"选项，`handleRecommendSearch()` (第 211 行) 调用 `recommendJobs()`。已验证无需额外改动。
2. **[P2]** 🔲 需做网页测试：Docker 启动 → 页面打开 → 选"统一推荐接口"模式 → 输入中文查询 → 检查返回结果 → 浏览器控制台无报错

### 2.3 `/graph` — 全景图谱页

**负责：卫昊朗**

**状态：mock-only**

- 调用 `getCapabilityGraph()` 返回 `graphData`（Mock）
- 使用 Three.js GalaxyScene 做 3D 可视化
- 有技术栈/层级/年份筛选器

**缺口：**
1. **[严重]** 后端无图谱可视化 API——需新增接口返回 nodes/edges 结构
2. 卫昊朗需要设计 API 返回格式以匹配前端 `GalaxyScene` 的数据期望

### 2.4 `/recruitment` — 企业端岗位管理页

**负责：甘可欣**

**状态：mock-only**

- `getRecruitmentJobs()` → mock `recruitmentJobsData`
- `saveRecruitmentJob()` → mock 本地更新

**缺口：**
1. **[严重]** 需要后端岗位 CRUD API 对接——部分可复用 `/jobs/` CRUD，但需确认返回字段
2. 需要岗位状态管理（招聘中/草稿/已暂停）

### 2.5 `/candidates` — 企业端候选人匹配页

**负责：甘可欣**

**状态：mock-only**

- `getJobCandidates(jobId)` → mock `recruitmentCandidatesData`
- `updateCandidateStage()` → mock 本地更新
- 简历导入功能是前端模拟的

**缺口：**
1. **[严重]** 需要 "岗位→候选人列表" 反向推荐接口
2. 需要候选人阶段变更接口（待筛选/待沟通/入围/不匹配）

### 2.6 `/signals` (DiscoveryPage) — 岗位市场雷达页

**负责：甘可欣/卫昊朗**

**状态：partial-live**

- `getMarketRuntimeStatus()` → 真实 `/ingestion/stats` + `/bm25/stats`
- `getDiscoveryCandidates()` → mock
- `importMarketCsv()` → 真实 `POST /csv/ingest-csv`

**缺口：**
1. 市场趋势数据大部分仍是 Mock
2. 需确认 `/ingestion/stats` 和 `/bm25/stats` 返回的统计数据是否足够

### 2.7 `/learning` (LearningPlanPage) — 学习路径页

**负责：叶骑瑞**

**状态：mock-only**

- `getLearningPlan()` → mock `learningPlanData`

**缺口：**
1. **[严重]** 后端无学习路径接口——需全新设计
2. 需要：目标岗位、缺失技能、技能优先级、学习阶段、学习建议、推荐资源

### 2.8-2.15 旧页面

| 路由 | 页面 | 状态 | 缺口 |
|------|------|------|------|
| `/` | WorkspaceHomeRedirect | 重定向到 /diagnosis 或 /recruitment | 无 |
| `/search` | SearchPage | 旧 hybrid search | 英文市场，未迁移到新接口 |
| `/job/:jobId` | JobDetailsPage | 旧 CRUD | 基本可用 |
| `/upload-resume` | ResumeUploadPage | 旧上传 | 基本可用 |
| `/recommendations` | RecommendationsPage | 旧推荐 | 极简 UI，缺字段 |
| `/personalized-recommendations` | PersonalizedRecommendationsPage | 旧 reranking | 与 recommendations 重叠 |
| `/login` | LoginPage | Auth | 基本可用 |
| `/register` | RegisterPage | Auth | 基本可用 |

---

## 3. 纪雨涵负责页面 — 行动清单

按分工4.md，我负责 `/fusion-demo`、`/search`、`/recommendations` + 维护缺口文档。

| 优先级 | 行动 | 状态 |
|--------|------|------|
| **P0** | ✅ 梳理全前端接口状态 → 本文档 | ✅ 已完成 |
| **P1** | ✅ `/fusion-demo` 中 `/fusion/recommend` 已是显式模式（Segmented "统一推荐接口"，代码第 343 行） | ✅ 已验证（2026-08-06） |
| **P1** | `/fusion-demo` 网页测试：打开页面、统一推荐真实搜索、检查返回 | 🔲 待做（需 Docker） |
| **P2** | ✅ 检查 `/search` — 结论：暂不迁移 | ✅ 已完成（2026-08-06，见下方分析） |
| **P2** | ✅ 检查 `/recommendations` — 结论：暂不迁移 | ✅ 已完成（2026-08-06，见下方分析） |
| **P3** | ✅ 修复旧 `api.js` 的 `API_BASE_URL` — 已使用 `/api/v1`（第 4 行），无需修改 | ✅ 已验证（2026-08-06） |

### 3.1 `/search` 迁移评估（2026-08-06）

**现状：**
- 调用 `searchJobs()` → `POST /jobs/search`（旧 hybrid search）
- 支持关键词提取 + 重排：`extractKeywords()` + `rerankWithKeywords()`
- 有 Mock 降级：`is_mock_data` 检测 + 警告横幅（SearchPage.js 第 788-796 行）
- 全英文：示例查询、地点（San Francisco/New York/Seattle）、薪资格式（USD）、签证（H1B）

**暂不迁移的理由：**
1. **市场不同**：该页面面向美国/英文市场，新融合管线使用中国标准数据集（中文岗位）
2. **旧接口仍可用**：`POST /jobs/search` 和 `/reranking/search-reranked` 后端端点仍然存在
3. **迁移成本高**：需将整个页面适配中文数据、替换 API 调用为 `/fusion/recommend`、更新 JobCard 展示融合分项得分
4. **优先级低**：当前团队重点是中国市场岗位匹配，英文搜索页面不是核心交付物

**后续迁移时机：** 等中国岗位数据稳定后，可规划英文市场支持的独立阶段。

### 3.2 `/recommendations` + `/personalized-recommendations` 迁移评估（2026-08-06）

**现状：**
- `/recommendations`：调用 `getJobRecommendations()` → `POST /jobs/recommendations`，极简 UI（不显示岗位标题/公司名，只显示 "Job #1"）
- `/personalized-recommendations`：调用 `getPersonalizedRecommendations()` → `POST /reranking/personalized-recommendations`，较完整 UI（岗位标题、公司名、地点、薪资、技能标签）

**暂不迁移的理由：**
1. **两页面功能重叠**：都是"上传简历→推荐岗位"，应合并为一个页面后再迁移
2. **旧管线仍可用**：两个旧端点仍存在并可响应
3. **UI 需重做**：`/recommendations` 缺少核心展示字段（岗位标题、公司名），`/personalized-recommendations` 使用 `rerank_score` 而非新 `final_score`
4. **迁移路径明确**：合并 → 替换 API 为 `/fusion/recommend` → 展示分层融合得分（final_score + bm25/semantic/skill/graph 分项）

**建议：** 先与韩耀栋确认 `/fusion/recommend` 能否完全替代旧 `/jobs/recommendations` 和 `/reranking/personalized-recommendations`。如果可以，在后续阶段合并两个页面并统一迁移。

---

## 4. 其他成员缺口汇总（供协调用）

| 负责人 | 页面 | 最关键缺失 |
|--------|------|-----------|
| 叶骑瑞 | `/diagnosis` | 全链路已通 ✅，需验证实际上传流程 |
| 叶骑瑞 | `/learning` | 学习路径 API 完全缺失 |
| 卫昊朗 | `/graph` | 图谱可视化 API 缺失，需定义 nodes/edges 格式 |
| 甘可欣 | `/recruitment` | 岗位管理 API 缺失（部分可复用 /jobs/ CRUD） |
| 甘可欣 | `/candidates` | 候选人匹配 API 缺失 |
| 甘可欣/卫昊朗 | `/signals` | 市场趋势数据大部分 Mock |

---

## 5. 后端新接口（上游 `fa9f6c5` 新增）

| 接口 | commit | 说明 |
|------|--------|------|
| `POST /fusion/recommend` | `4456264` | 统一推荐入口，参数：candidate_id, query_text, top_k, candidate_pool, mode, source_type, layered_weights |
| 前端 `recommendJobs()` | `1816e03` | fusionApi.js 已对接 |
| FusionDemoPage 更新 | `1816e03` | import recommendJobs |

---

## 6. 共性问题（更新）

1. **API_BASE_URL 已统一** ✅：`api.js`（第 4 行）、`fusionApi.js`（第 8 行）、`intelligenceApi.js` 统一使用 `/api/v1` 相对路径
2. **Mock 数据全英文**：旧页面（search/recommendations）的 Mock 仍是英文，新页面（diagnosis/graph/recruitment）已有中文 Mock ✅
3. **旧页面未整合到新 WorkbenchLayout 导航中**：旧页面路由存在但 WorkbenchLayout 的侧边栏不展示它们
4. **两套推荐体系并存**：新 `/fusion/recommend` vs 旧 `/jobs/recommendations` + `/reranking/personalized-recommendations`
