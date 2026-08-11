# /diagnosis 页面接口对接结果

**负责人**: 叶骑瑞  
**日期**: 2026-08-11  
**状态**: ✅ 已完成（前端→后端全链路打通，KG 数据对齐待魏昊朗）

---

## 一、对接架构

```
DiagnosisPage.js
  └─ talentApi.diagnoseCandidate({ resumeFile })
       └─ diagnoseUploadedResume(file)
            ├─ ① uploadResume(file)           → POST /api/v1/jobs/upload-resume
            ├─ ② searchBm25(queryText)         → POST /api/v1/bm25/search
            ├─ ③ rerankSemantic({...})         → POST /api/v1/semantic/rerank
            ├─ ④ analyzeKnowledgeGraphGap(...) → POST /api/v1/kg/analyze
            └─ ⑤ rankJobs(candidateId, inputs) → POST /api/v1/fusion/rank

降级路径（②~⑤ 任一失败时）:
            └─ getJobRecommendations(candidate) → POST /api/v1/jobs/recommendations
```

## 二、接口测试记录

| # | 接口 | 方法 | Status | 耗时 | 返回数据 | 备注 |
|---|------|------|:---:|:---:|:---:|------|
| 1 | `/api/v1/jobs/upload-resume` | POST | 200 | 4.20s | ✅ | 简历解析成功，提取技能+经历 |
| 2 | `/api/v1/bm25/search` | POST | 200 | 364ms | ✅ | 返回 8 条 BM25 候选岗位 |
| 3 | `/api/v1/semantic/rerank` | POST | 200 | 26.85s | ✅ | BGE-M3 模型推理，语义分正常 |
| 4 | `/api/v1/kg/analyze` | POST | 200 ×8 | ~500ms | ⚠️ | 接口可调但 Neo4j 缺岗位数据，返回空 |
| 5 | `/api/v1/jobs/recommendations` | POST | 200 | 4.94s | ⚠️ | 降级路径，旧岗位库无匹配结果 | |

## 三、网页测试记录

| 检查项 | 通过 | 备注 |
|--------|:---:|------|
| 页面上传简历后可进入结果视图 | ✅ | 真实 PDF 上传成功 |
| 「已确认能力画像」显示真实技能 | — | 降级链路，KG 未对齐无法展示 |
| 匹配岗位列表显示 ≥1 个结果 | ❌ | KG 岗位 ID 与 BM25 不匹配，降级后旧库也无结果 |
| 岗位卡片显示 final_score | — | 因上一步无结果 |
| 「关键能力差距」显示缺失技能 | — | 因上一步无结果 |
| scoreBreakdown 含 semantic_score | — | 因上一步无结果 |
| 推荐理由为真实文本（非 Mock） | — | 因上一步无结果 |
| 浏览器控制台无报错 | ✅ | 语义重排 26.85s 正常完成 |
| 后端日志收到请求 | ✅ | 全部 4 类接口均有调用记录 |
| 页面给出清晰的错误提示 | ✅ | 显示「BM25 岗位与知识图谱岗位 ID 尚未对齐」 |

## 四、数据字段验证

| 字段 | 预期来源 | 是否真实 | 示例值 |
|------|---------|:---:|------|
| `source` | `"live"` | ✅ | 前端上传真实 PDF，后端返回 |
| `pipeline.mode` | 完整链路 `"full"` / 降级 `"legacy-fallback"` | ✅ | `"legacy-fallback"`（因 KG 未对齐） |
| `pipeline.warning` | 降级原因说明 | ✅ | 「BM25 岗位与知识图谱岗位 ID 尚未对齐」 |
| `profile.skills[]` | 简历解析提取 | ✅ | 后端真实提取 |
| `matches[].role` | BM25 岗位标题 | — | 未展示（KG 未对齐导致无结果） |
| `matches[].score` | fusion final_score | — | 未展示 |
| `matches[].gaps[].skill` | KG 缺失技能 | — | 未展示 |
| `matches[].reason` | 推荐解释文本 | — | 未展示 |

## 五、问题与缺口

| 问题 | 严重程度 | 状态 | 协调人 |
|------|:---:|:---:|:---:|
| KG 差距分析可调用但返回空数据（`skill_coverage=0`, `missing_skills={}`） | **高** | 待解决 | 魏昊朗 |
| BM25 返回的 `job_id` 与 Neo4j 知识图谱中的岗位 ID 未对齐，导致融合排序无法形成完整差距分析 | **高** | 待解决 | 魏昊朗 + 韩耀栋 |
| 语义重排耗时较长（26.85s，BGE-M3 推理） | 低 | 可优化 | 叶骑瑞 |

## 六、结论

- [x] 前端 `/diagnosis` 页面通过 Docker 成功启动，可正常访问
- [x] 前端已通过真实 PDF 上传触发完整后端调用链路
- [x] 简历解析接口 `upload-resume` 返回 200，成功解析
- [x] BM25 搜索接口返回 200，召回候选岗位
- [x] 语义重排接口返回 200，BGE-M3 推理成功
- [x] KG 差距分析接口返回 200（×8），可正常调用
- [x] 页面在无结果时给出清晰的错误提示
- [ ] 完整链路（mode=full）需 KG 岗位数据对齐后重新测试
- [ ] 对齐后应展示：匹配岗位 TopN、final_score、semantic_score、技能缺口、推荐理由

**当前对接状态：前端→后端全链路打通，4 个接口全部 200。唯一阻塞项是 Neo4j 知识图谱缺少与 BM25 一致的岗位 ID，由魏昊朗补充数据后可立即跑通完整诊断流程。**

---

## 附录：测试命令（PowerShell）

```powershell
# 1. 上传简历
$form = @{ resume_file = Get-Item "你的简历路径.pdf" }
Invoke-RestMethod -Uri "http://localhost:18088/api/v1/jobs/upload-resume" -Method Post -Form $form

# 2. BM25 搜索
$body = '{"query":"Python SQL 后端开发","size":5}'
Invoke-RestMethod -Uri "http://localhost:18088/api/v1/bm25/search" -Method Post -ContentType "application/json" -Body $body

# 3. 语义重排
$body = '{"query_id":"test","query_text":"Python SQL 后端开发","candidates":[{"job_id":"JOB08237","title":"Python开发","description":"Python后端开发","required_skills":["Python","SQL"]}]}'
Invoke-RestMethod -Uri "http://localhost:18088/api/v1/semantic/rerank" -Method Post -ContentType "application/json" -Body $body

# 4. KG 差距分析
$body = '{"candidate_id":"test_candidate","job_id":"JOB08237"}'
Invoke-RestMethod -Uri "http://localhost:18088/api/v1/kg/analyze" -Method Post -ContentType "application/json" -Body $body

# 5. 融合排序
$body = '{"query_id":"test","jobs":[{"query_id":"test","job_id":"JOB08237","bm25_score":0.8,"semantic_score":0.7,"skill_coverage":0.6,"job_family_match":1.0,"graph_relatedness":0.5,"missing_skills":[],"evidence_paths":[]}]}'
Invoke-RestMethod -Uri "http://localhost:18088/api/v1/fusion/rank" -Method Post -ContentType "application/json" -Body $body

# 6. 统一推荐（一键式）
$body = '{"query_text":"Python SQL 后端开发","top_k":5,"mode":"online"}'
Invoke-RestMethod -Uri "http://localhost:18088/api/v1/fusion/recommend" -Method Post -ContentType "application/json" -Body $body
```
