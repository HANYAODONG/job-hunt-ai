# Iteration 08: Workflow 2 text2vec 轻量语义重排

## 背景

工作流 2 使用 text2vec-base-chinese 作为轻量语义 baseline，对 BM25 Top200
候选集做余弦相似度重排；同时提供 BGE-M3 对照组，用于在同一金标集上公平对比
效果和资源占用。

## 新增文件

| 文件 | 职责 |
|---|---|
| `backend-src/app/services/text2vec_embedding_service.py` | text2vec 嵌入服务封装 |
| `backend-src/scripts/rerank_semantic_text2vec.py` | 核心：离线编码 + BM25 Top200 重排 |
| `backend-src/scripts/rerank_semantic_bge.py` | BGE-M3 对照组（相同流水线） |
| `backend-src/scripts/evaluate_semantic_rerank.py` | 评测与三模型对比 |

## 运行流程

```powershell
# 1. 确保 BM25 候选集已生成
docker compose up -d elasticsearch
python .\backend-src\scripts\index_chinese_jobs.py --recreate
python .\backend-src\scripts\retrieve_bm25_candidates.py --size 200

# 2. text2vec 语义重排
python .\backend-src\scripts\rerank_semantic_text2vec.py

# 3. BGE-M3 对照组（可选，需要更多内存）
python .\backend-src\scripts\rerank_semantic_bge.py

# 4. 三模型评测对比
python .\backend-src\scripts\evaluate_semantic_rerank.py --compare-all
```

## 数据流

```
jobs.jsonl (工作流 1)
    │
    ├──→ rerank_semantic_text2vec.py
    │       ├── 离线: text2vec 编码岗位 → artifacts/semantic_text2vec/jobs_embeddings.npy
    │       └── 在线: 读 BM25 Top200 → 余弦重排 → semantic_rerank_top200.jsonl
    │
    └──→ rerank_semantic_bge.py
            ├── 离线: BGE-M3 编码岗位 → artifacts/semantic_bge/jobs_embeddings.npy
            └── 在线: 读 BM25 Top200 → 余弦重排 → semantic_rerank_top200.jsonl

evaluate_semantic_rerank.py
    ├── 读取 text2vec + BGE + BM25 排名
    ├── 读取 label_pairs_gold.jsonl
    └── 输出 eval_report.json（对比表）
```

## 模型选择

- **默认**: `shibing624/text2vec-base-chinese` (~400MB, CPU 友好)
- **对照组**: `BAAI/bge-m3` (~2.2GB, 需要更多内存)

## 岗位文本拼接模式

| 模式 | 说明 |
|---|---|
| `title_only` | 仅岗位标题 |
| `title+requirements` | 标题 + 岗位要求 |
| `title+duty+requirements+skills` | 标题 + 职责 + 要求 + 技能（默认） |

## 验收标准

- [x] 模型在普通本地环境运行
- [x] 岗位向量可重复生成并缓存
- [x] 读取 BM25 Top200 候选集
- [x] 输出 semantic_score 和 semantic_rank
- [x] 对比 BM25、BM25 + text2vec、BM25 + BGE-M3
- [x] 报告 Recall@K、MRR、NDCG@K、编码耗时、峰值内存
