# 第十二次迭代：诊断页面对接、学习路径缺口与语义模型对比实验

**负责人**：叶骑瑞  
**日期**：2026-08-11  
**对应分工**：`docs/分工4.md` 第四节

---

## 迭代目的

按第四阶段分工要求，完成求职者端三个模块：

1. `/diagnosis` 人岗诊断页接入真实后端结果
2. `/learning` 学习路径页缺口说明
3. text2vec / BGE-M3 语义重排 + 五组消融实验

---

## 一、`/diagnosis` 人岗诊断页对接

### 1.1 对接架构

```
DiagnosisPage.js
  └─ talentApi.diagnoseCandidate({ resumeFile })
       └─ diagnoseUploadedResume(file)
            ├─ ① uploadResume(file)           → POST /api/v1/jobs/upload-resume
            ├─ ② searchBm25(queryText)         → POST /api/v1/bm25/search
            ├─ ③ rerankSemantic({...})         → POST /api/v1/semantic/rerank
            ├─ ④ analyzeKnowledgeGraphGap(...) → POST /api/v1/kg/analyze
            └─ ⑤ rankJobs(candidateId, inputs) → POST /api/v1/fusion/rank

降级路径（任一失败时）:
            └─ getJobRecommendations(candidate) → POST /api/v1/jobs/recommendations
```

### 1.2 对接结果

| 接口 | 方法 | Status | 耗时 | 数据 | 说明 |
|------|------|:---:|:---:|:---:|------|
| `upload-resume` | POST | 200 | 4.20s | ✅ | 简历解析成功，提取技能+经历 |
| `bm25/search` | POST | 200 | 364ms | ✅ | ES 索引 `bigcompany_jobs_v1`，5886 岗位 |
| `semantic/rerank` | POST | 200 | 26.85s | ✅ | BGE-M3 模型，实时光推理 |
| `kg/analyze` | POST | 200 ×8 | ~500ms | ⚠️ | 接口可调但 Neo4j 无候选人/岗位数据 |
| `jobs/recommendations` | POST | 200 | 4.94s | ⚠️ | 降级路径，旧岗位库无匹配 |

### 1.3 当前状态

- 前端→后端全链路打通，4 个接口全部 200
- 前端正确展示错误信息：「BM25 岗位与知识图谱岗位 ID 尚未对齐」
- **阻塞项**：Neo4j 缺少与 ES 一致的岗位数据（魏昊朗 + 韩耀栋协调）

### 1.4 交付物

- `docs/diagnosis-api-integration-result.md` — 完整接口测试记录

---

## 二、`/learning` 学习路径页缺口说明

### 2.1 当前状态

- 页面路径：`/learning`
- 数据来源：前端 Mock（`mockTalentData.learningPlanData`）
- 后端接口：无

### 2.2 缺口清单

| 字段 | 类型 | 优先级 | 说明 |
|------|------|:---:|------|
| `target_role` | string | P0 | 目标岗位名称 |
| `missing_skills` | string[] | P0 | 缺失技能列表 |
| `skill_priority` | object | P1 | 技能优先级 |
| `stages[].title` | string | P0 | 阶段标题 |
| `stages[].skill` | string | P0 | 对应学习技能 |
| `stages[].goal` | string | P0 | 阶段目标 |
| `stages[].tasks` | string[] | P0 | 具体任务 |
| `stages[].duration` | string | P1 | 预计耗时 |
| `stages[].outcome` | string | P1 | 预期交付物 |
| `learning_suggestions` | string[] | P2 | 学习建议 |
| `recommended_resources` | object[] | P2 | 推荐学习资源 |

建议后端接口：`POST /api/v1/learning/plan`，由大模型根据技能缺口动态生成，不可用时降级为规则模板。

### 2.3 交付物

- `docs/learning-gap.md` — 完整缺口说明文档

---

## 三、语义重排实验

### 3.1 模型配置

| 项目 | text2vec | BGE-M3 |
|------|---------|--------|
| 模型 | `shibing624/text2vec-base-chinese-sentence` | `BAAI/bge-m3` |
| 大小 | 449.9 MB | ~2.2 GB |
| 维度 | 768d | 1024d |
| 加载耗时 | 12.1s | 20.0s |
| 岗位编码（3208条） | 485.9s | 3,661s |
| 平均查询耗时 | 102ms | 278ms |
| 设备 | CPU | CPU |

### 3.2 运行命令

```powershell
# text2vec
docker exec -it jobmatch_backend python scripts/rerank_semantic_text2vec.py

# BGE-M3
docker exec -it jobmatch_backend python scripts/rerank_semantic_bge.py `
  --bm25 /app/artifacts/bm25/bm25_top50_1000.jsonl
```

### 3.3 产物

```
artifacts/semantic_text2vec/
  ├── jobs_embeddings.npy
  ├── jobs_embedding_ids.json
  ├── semantic_rerank_top200.jsonl
  └── run_metadata.json

artifacts/semantic_bge/
  ├── jobs_embeddings.npy
  ├── jobs_embedding_ids.json
  ├── semantic_rerank_top200.jsonl
  └── run_metadata.json
```

---

## 四、融合消融实验

### 4.1 实验设计

五组对比实验：

```
① BM25 baseline
② BM25 + text2vec
③ BM25 + BGE（替换 text2vec 为 BGE-M3）
④ BM25 + BGE + 技能覆盖
⑤ BM25 + BGE + 技能覆盖 + 图谱特征
```

### 4.2 运行命令

```powershell
# text2vec 消融
docker exec -it jobmatch_backend python scripts/run_fusion_pipeline.py `
  --bm25-input /app/artifacts/bm25/bm25_top50_1000.jsonl `
  --semantic-input /app/artifacts/semantic_text2vec/semantic_rerank_top200.jsonl `
  --preset all --limit 1000

# BGE 消融
docker exec -it jobmatch_backend python scripts/run_fusion_pipeline.py `
  --bm25-input /app/artifacts/bm25/bm25_top50_1000.jsonl `
  --semantic-input /app/artifacts/semantic_bge/semantic_rerank_top200.jsonl `
  --preset all --limit 1000
```

### 4.3 结果摘要

| 实验组 | 语义源 | 均分 | 优秀(≥0.7) | 良好(0.5-0.7) | 较低(<0.3) |
|--------|:---:|:---:|:---:|:---:|:---:|
| ① BM25 | — | 0.5583 | 32% | 31% | 24% |
| ② BM25 + text2vec | text2vec | **0.7539** | **63%** | 22% | **0%** |
| ③ BM25 + BGE | BGE-M3 | 0.5902 | 12% | 59% | 17% |
| ④ + 技能覆盖 | BGE-M3 | 0.5902 | 12% | 59% | 17% |
| ⑤ + 图谱 | BGE-M3 | 0.5902 | 12% | 59% | 17% |

> ④⑤与③同值：Neo4j 无数据，`skill_coverage` 和 `graph_relatedness` 均为 0。

### 4.4 关键发现

- **text2vec 显著优于 BGE-M3**：融合后均分提升 35%（0.56→0.75），消除所有低于 0.3 的结果
- BGE-M3 仅提升 6%（0.56→0.59），余弦值偏低（0.4-0.8 vs text2vec 0.85-0.95）
- text2vec 轻量（450MB）、快速（102ms/条），适合 CPU 环境；BGE 需 GPU

---

## 五、离线评测（Recall / MRR / NDCG）

| 指标 | 状态 | 原因 |
|------|:---:|------|
| Recall@K | 待产出 | 金标 job_id 与排名结果 job_id 不匹配 |
| MRR | 待产出 | 同上 |
| NDCG@K | 待产出 | 同上 |

> 评测脚本运行正常（600 标注对、30 个 query），但 `mean_labeled_candidates: 0.0`，需韩耀栋确认金标标注时使用的岗位池后重新对齐。

---

## 六、交付物汇总

| 交付物 | 文件路径 | 状态 |
|--------|---------|:---:|
| `/diagnosis` 接口对接结果 | `docs/diagnosis-api-integration-result.md` | ✅ |
| `/learning` 缺口说明 | `docs/learning-gap.md` | ✅ |
| 语义重排产物 | `artifacts/semantic_text2vec/` | ✅ |
| 语义重排产物 | `artifacts/semantic_bge/` | ✅ |
| 融合消融产物 | `artifacts/fusion/` | ✅ |
| 模型实验记录 | `docs/model-experiment-results.md` | ✅ |
| 本迭代记录 | `docs/iterations/iteration-12-diagnosis-learning-semantic.md` | ✅ |

---

## 七、遗留问题

| 问题 | 严重程度 | 协调人 |
|------|:---:|:---:|
| Neo4j 无岗位/候选人数据，技能覆盖和图谱因子为 0 | 高 | 魏昊朗 |
| 金标 job_id 与排名 job_id 不匹配，离线评测指标为 0 | 高 | 韩耀栋 |
| `/learning` 后端接口缺失 | 中 | 韩耀栋（分配） |
| BGE-M3 CPU 推理过慢（278ms/条），不可用于在线 | 低 | — |

---

## 八、经验总结

1. **Docker 路径问题**：容器内脚本解析 `REPO_ROOT` 可能指向 `/` 而非 `/app`，需显式传 `--input` 等参数
2. **Windows 命令差异**：PowerShell 的 `curl` 是 `Invoke-WebRequest` 别名，JSON 传参需用 `$body` 变量 + `Invoke-RestMethod`，或使用 `curl.exe`
3. **npm 超时**：Docker 构建前端时需配国内镜像 `npm config set registry https://registry.npmmirror.com`
4. **前端诊Mock触发**：`DiagnosisPage` 示例按钮不走后端，必须拖拽真实 PDF 文件才能看到 API 调用
