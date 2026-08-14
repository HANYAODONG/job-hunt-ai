# 语义模型对比实验结果

**负责人**: 叶骑瑞  
**日期**: 2026-08-11  
**状态**: ✅ 语义重排 + 融合消融实验全部完成

---

## 一、实验环境

| 项目 | 值 |
|------|-----|
| 岗位索引 | `bigcompany_jobs_v1`，ES 5886 岗位 |
| BM25 候选集 | `bm25_top50_1000.jsonl`（1000 条简历 × 50 候选） |
| 岗位向量库 | `jobs_candidates.jsonl`（3208 岗位） |
| 评测标签 | `label_pairs_gold.jsonl`（600 标注对） |
| 运行设备 | CPU（Docker 容器） |

---

## 二、语义重排运行命令

```powershell
# text2vec 语义重排
docker exec -it jobmatch_backend python scripts/rerank_semantic_text2vec.py

# BGE-M3 语义重排
docker exec -it jobmatch_backend python scripts/rerank_semantic_bge.py `
  --bm25 /app/artifacts/bm25/bm25_top50_1000.jsonl

# 三模型对比评测（金标 job_id 对齐中，当前指标待产出）
docker exec -it jobmatch_backend python scripts/evaluate_semantic_rerank.py --compare `
  --rankings `
    "/app/artifacts/bm25/bm25_top50_1000.jsonl:bm25_score:bm25_rank:BM25" `
    "/app/artifacts/semantic_text2vec/semantic_rerank_top200.jsonl:semantic_score:semantic_rank:text2vec" `
    "/app/artifacts/semantic_bge/semantic_rerank_top200.jsonl:semantic_score:semantic_rank:BGE-M3" `
  --labels /app/artifacts/dataset_iteration_05/label_pairs_gold.jsonl

# 融合消融实验（text2vec）
docker exec -it jobmatch_backend python scripts/run_fusion_pipeline.py `
  --bm25-input /app/artifacts/bm25/bm25_top50_1000.jsonl `
  --semantic-input /app/artifacts/semantic_text2vec/semantic_rerank_top200.jsonl `
  --preset all --limit 1000

# 融合消融实验（BGE）
docker exec -it jobmatch_backend python scripts/run_fusion_pipeline.py `
  --bm25-input /app/artifacts/bm25/bm25_top50_1000.jsonl `
  --semantic-input /app/artifacts/semantic_bge/semantic_rerank_top200.jsonl `
  --preset all --limit 1000
```

---

## 三、模型资源占用

| 指标 | text2vec | BGE-M3 |
|------|:---:|:---:|
| 模型 | `shibing624/text2vec-base-chinese-sentence` | `BAAI/bge-m3` |
| 模型大小 | 449.9 MB | ~2.2 GB |
| 向量维度 | 768 | 1024 |
| 加载耗时 | 12.1s | 20.0s |
| 岗位编码耗时（3208条） | 485.9s | 3,661s |
| 平均查询编码耗时 | 102.2ms | 277.7ms |
| 设备 | CPU | CPU |

---

## 四、融合消融实验结果

### 4.1 五组对比（text2vec 语义）

| 实验组 | 预设 | 均分 | 优秀(≥0.7) | 良好(0.5-0.7) | 一般(0.3-0.5) | 较低(<0.3) |
|--------|------|:---:|:---:|:---:|:---:|:---:|
| ① BM25 baseline | `bm25-only` | 0.5583 | 16,007 (32%) | 15,726 (31%) | 6,394 (13%) | 11,873 (24%) |
| ② BM25 + text2vec | `bm25-semantic` | **0.7539** | **31,417 (63%)** | 11,009 (22%) | 7,574 (15%) | 0 |
| ③ + 技能覆盖 | `bm25-semantic-skill` | 0.7539 | 31,417 (63%) | 11,009 (22%) | 7,574 (15%) | 0 |
| ④ + 图谱特征（BGE） | — | — | — | — | — | — |
| ⑤ 全因子（full） | `full` | 0.7539 | 31,417 (63%) | 11,009 (22%) | 7,574 (15%) | 0 |

> ③④⑤ 与②同值：因 KG 数据缺失，`skill_coverage` 和 `graph_relatedness` 均为 0，无额外信息增益。

### 4.2 五组对比（BGE-M3 语义）

| 实验组 | 预设 | 均分 | 优秀(≥0.7) | 良好(0.5-0.7) | 一般(0.3-0.5) | 较低(<0.3) |
|--------|------|:---:|:---:|:---:|:---:|:---:|
| ① BM25 baseline | `bm25-only` | 0.5583 | 16,007 (32%) | 15,726 (31%) | 6,394 (13%) | 11,873 (24%) |
| ② BM25 + BGE | `bm25-semantic` | 0.5902 | 5,841 (12%) | **29,474 (59%)** | 6,243 (12%) | 8,442 (17%) |
| ③ + 技能覆盖 | `bm25-semantic-skill` | 0.5902 | 5,841 (12%) | 29,474 (59%) | 6,243 (12%) | 8,442 (17%) |
| ④ + 图谱特征 | `full` | 0.5902 | 5,841 (12%) | 29,474 (59%) | 6,243 (12%) | 8,442 (17%) |

### 4.3 text2vec vs BGE 关键对比

| 指标 | BM25-only | +text2vec | +BGE-M3 | 增量(text2vec) | 增量(BGE) |
|------|:---:|:---:|:---:|:---:|:---:|
| 均分 | 0.5583 | **0.7539** | 0.5902 | **+0.1956** | +0.0319 |
| 优秀占比 | 32% | **63%** | 12% | **+31%** | -20% |
| 较低占比 | 24% | **0%** | 17% | **-24%** | -7% |

> **结论**：text2vec 语义分数（余弦 0.89-0.93）远高于 BGE-M3（0.50-0.80），融合后 text2vec 组均分提升 35%，BGE 组仅提升 6%。

---

## 五、离线评测指标（Recall / MRR / NDCG）

| 实验组 | Recall@5 | Recall@10 | MRR | NDCG@10 | 备注 |
|--------|:---:|:---:|:---:|:---:|------|
| BM25 baseline | — | — | — | — | 待产出 |
| BM25 + text2vec | — | — | — | — | 待产出 |
| BM25 + BGE | — | — | — | — | 待产出 |
| BM25 + BGE + 技能覆盖 | — | — | — | — | 待产出 |
| BM25 + BGE + 技能覆盖 + 图谱 | — | — | — | — | 待产出 |

> ⚠️ 评测指标当前全为 0.0：金标 `label_pairs_gold.jsonl` 中的 `job_id` 与 BM25/语义排名结果中的 `job_id` 来自不同岗位池，无交集。需韩耀栋协调金标标注时使用的岗位源，重新对齐后补测。详情见第五节「已知限制」。

---

## 六、已知限制

| 问题 | 影响 | 协调人 |
|------|------|:---:|
| 金标 job_id 与排名结果 job_id 不匹配 | Recall/MRR/NDCG 无法计算 | 韩耀栋 |
| Neo4j 无候选人/岗位节点 | `skill_coverage` 和 `graph_relatedness` 均为 0 | 魏昊朗 |
| BGE-M3 CPU 推理极慢（277ms/条，是 text2vec 的 2.7 倍） | 大规模在线场景不可用，需 GPU | — |
| BGE 余弦相似度数值偏低（0.4-0.8 vs text2vec 0.85-0.95） | 融合时与 BM25 分值尺度不匹配 | — |
