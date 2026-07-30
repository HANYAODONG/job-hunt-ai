# 工作流4：融合排序 — 接口与接入说明

**负责人**：纪雨涵  
**代码位置**：`backend-src/app/api/endpoints/fusion.py`、`backend-src/app/services/fusion_scoring_service.py`、`backend-src/app/services/fusion_merge_service.py`

---

## 一、融合公式

```
final_score = w1 × bm25_score + w2 × semantic_score + w3 × skill_coverage
            + w4 × job_family_match + w5 × graph_relatedness
```

默认权重：`bm25=0.15, semantic=0.25, skill_coverage=0.30, job_family=0.15, graph=0.15`（权重之和=1.0，可通过 API 动态调整）

---

## 二、API 端点

所有路径前缀：`/api/v1/fusion`

### 2.1 在线融合排序（查询 → BM25 → 融合）

```
POST /rank-from-query
```

请求：
```json
{
  "query_text": "熟悉 Python、SQL、数据分析，3年经验",
  "size": 20,
  "weights": {"bm25": 0.15, "semantic": 0.25, "skill_coverage": 0.30, "job_family": 0.15, "graph": 0.15},
  "source_type": null
}
```

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `query_text` | string | ✅ | 查询文本（简历 summary 或自由文本） |
| `size` | int (5-200) | 否 | BM25 召回数量，默认 20 |
| `weights` | object | 否 | 自定义权重，不传则用服务端默认值 |
| `source_type` | string | 否 | `enterprise` 或 `government`，不传则不限 |
| `query_id` | string | 否 | 查询 ID，不传自动生成 |

### 2.2 批量融合排序（传入完整因子数据）

```
POST /rank
```

请求：
```json
{
  "query_id": "resume_001",
  "jobs": [
    {
      "query_id": "resume_001",
      "job_id": "JOB00001",
      "bm25_score": 0.76,
      "semantic_score": 0.82,
      "skill_coverage": 0.67,
      "job_family_match": 1.0,
      "graph_relatedness": 0.72,
      "missing_skills": ["PyTorch"],
      "evidence_paths": []
    }
  ]
}
```

### 2.3 单条融合评分

```
POST /score
```

请求：同 FusionInput 单条对象

### 2.4 Mock 模式（前端独立开发用）

```
POST /mock-rank
```

请求：
```json
{
  "query_id": "mock_resume_001",
  "num_jobs": 20,
  "seed": 42,
  "weights": null
}
```

### 2.5 权重管理

```
GET  /weights         # 查看当前权重和因子说明
PUT  /weights         # 修改权重（动态生效，无需重启）
POST /weights/reset   # 恢复默认权重
```

---

## 三、输入格式

### FusionInput（单条岗位的融合输入）

```json
{
  "query_id": "resume_001",
  "job_id": "JOB00001",
  "bm25_score": 0.76,
  "semantic_score": 0.82,
  "skill_coverage": 0.67,
  "job_family_match": 1.0,
  "graph_relatedness": 0.72,
  "missing_skills": ["PyTorch"],
  "evidence_paths": [
    "Candidate → HAS_SKILL → Python ← REQUIRES_SKILL ← Job"
  ]
}
```

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `query_id` | string | 公共 | 简历/查询 ID |
| `job_id` | string | 公共 | 岗位 ID |
| `bm25_score` | float (≥0) | W5 | BM25 得分，**建议归一化到 [0,1]** |
| `semantic_score` | float (0-1) | W2 | 语义余弦相似度 |
| `skill_coverage` | float (0-1) | W3 | 技能覆盖率 |
| `job_family_match` | float (0-1) | W3 | 岗位族匹配（同族=1.0） |
| `graph_relatedness` | float (0-1) | W3 | 知识图谱关联度 |
| `missing_skills` | string[] | W3 | 缺失技能列表 |
| `evidence_paths` | string[] | W3 | KG 证据路径 |

> **注意**：`bm25_score` 原始值可 >1（ES _score）。Merge 层会做 min-max 归一化，但如果你直接调 `/rank`，建议先归一化或传原始分数（融合层会按权重加权，不会因为量纲差异完全失真）。

---

## 四、输出格式

### FusionOutput

```json
{
  "query_id": "resume_001",
  "job_id": "JOB00001",
  "final_score": 0.79,
  "rank": 1,
  "score_breakdown": {
    "bm25": 0.76,
    "semantic": 0.82,
    "skill_coverage": 0.67,
    "job_family": 1.0,
    "graph": 0.72
  },
  "explanation": "该岗位与您的简历整体匹配度很高。✅ 强项：语义相似度（82%）、岗位大类匹配（100%）。⚠️ 无明显弱项。🔍 缺失技能：PyTorch。💡 建议：建议补充 PyTorch 等相关技能，可显著提升匹配度。",
  "missing_skills": ["PyTorch"],
  "evidence_paths": ["Candidate → HAS_SKILL → Python ← REQUIRES_SKILL ← Job"],
  "meta": {
    "title": "机器学习工程师",
    "company": "示例公司",
    "bm25_score_raw": 218.1
  }
}
```

### FusionBatchOutput（批量响应）

```json
{
  "query_id": "resume_001",
  "results": [ /* FusionOutput 数组，按 final_score 降序 */ ],
  "weights_used": {"bm25": 0.15, "semantic": 0.25, "skill_coverage": 0.30, "job_family": 0.15, "graph": 0.15}
}
```

---

## 五、其他工作流如何接入

### 方式 A：离线批处理（推荐联调方式）

各工作流产出独立的 JSONL 文件，W4 通过 `run_fusion_pipeline.py` 读取并融合：

| 文件 | 来源 | 格式 |
|---|---|---|
| `artifacts/bm25/bm25_top200.jsonl` | W5 | `{query_id, candidates: [{job_id, bm25_score, bm25_rank}]}` |
| `artifacts/semantic_index/semantic_rerank_output.jsonl` | W2 | `{query_id, candidates: [{job_id, semantic_score, semantic_rank}]}` |
| `artifacts/kg/kg_features.jsonl` | W3 | `{query_id, job_id, skill_coverage, job_family_match, graph_relatedness, missing_skills, evidence_paths}` |

```bash
# 离线消融实验（4组权重预设对比）
python backend-src/scripts/run_fusion_pipeline.py \
  --bm25-input artifacts/bm25/bm25_top200.jsonl \
  --semantic-input artifacts/semantic_index/semantic_rerank_output.jsonl \
  --kg-input artifacts/kg/kg_features.jsonl \
  --preset all
```

### 方式 B：在线 API（用于单条查询演示）

直接调 `/rank-from-query`，后端自动完成 BM25 → 归一化 → 融合。semantic/KG 因子届时通过 merge 层注入。

### 方式 C：传完整数据

调 `/rank`，把所有因子拼成 FusionInput 数组传入。

---

## 六、前端演示页

访问：`/fusion-demo`

- **BM25 真实模式**（默认）：输入查询文本 → ES 检索 → 融合排序 → 结果展示
- **Mock 模式**：纯前端数据，不依赖后端，用于 UI 开发
- 权重滑块实时调整，`BM25-Only` 一键切换（消融实验用）
- 每个因子标注数据来源：✅真实 / 🔸待接入 / 🔸模拟

---

## 七、离线消融实验

`run_fusion_pipeline.py` 支持 4 组权重预设：

| 预设 | 配置 | 用途 |
|---|---|---|
| `bm25-only` | bm25=1.0 | BM25 baseline |
| `bm25-semantic` | bm25=0.4, semantic=0.6 | + 语义重排 |
| `bm25-semantic-skill` | bm25=0.3, semantic=0.3, skill=0.4 | + 技能覆盖 |
| `full` | 默认 5 因子权重 | 全因子 |

---

## 八、注意事项

1. **BM25 分数归一化**：原始 ES `_score` 无上限，merge 层会自动 min-max 归一化到 [0,1]
2. **缺失因子**：如果某个因子暂未产出，对应字段填 `0.0` 即可，融合引擎不会报错
3. **job_id 对齐**：确保所有文件中的 `job_id` 与 `jobs.jsonl` 一致
4. **权重验证**：PUT /weights 会校验权重之和=1.0，偏差 >0.01 会拒绝
5. **模型 `extra: allow`**：FusionInput 和 FusionOutput 都允许额外字段（如 `_meta`），不会因多余字段报错
