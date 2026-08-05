# 工作流 2：语义重排 — 小样本运行指南

本文档面向低配置电脑 / 快速验证场景，使用 `sample_pack` 数据在 5 分钟内跑通 text2vec 语义重排全流程。

## 前置条件

- 已完成工作流 1，生成 `artifacts/dataset_iteration_05/sample_pack/`
- 已完成工作流 5 的 sample 模式，生成 `artifacts/bm25/bm25_sample_top200.jsonl`
- Elasticsearch 已启动（Docker 容器 `jobmatch_elasticsearch`）
- Docker 容器内已安装 `sentence-transformers` 且模型文件已缓存

## 小样本数据说明

| 文件 | 规模 | 用途 |
|------|------|------|
| `sample_pack/jobs_sample.jsonl` | ~10 条岗位 | text2vec 离线编码（岗位向量） |
| `sample_pack/candidate_profiles_sample.jsonl` | 5 条简历 | 工作流 5 的输入（已生成 BM25 候选集） |
| `bm25/bm25_sample_top200.jsonl` | 5 × 50 = 250 对 | 语义重排的在线输入 |
| `sample_pack/label_pairs_gold_sample.jsonl` | ~10 对标注 | 评测 ground truth |

## 第一步：启动 Elasticsearch

```powershell
docker compose up -d elasticsearch
```

## 第二步：建立 sample 岗位的 ES 索引

```bash
# 进入 Docker 容器
docker exec -it jobmatch_backend bash

# 建索引
python scripts/index_chinese_jobs.py \
    --input artifacts/dataset_iteration_05/sample_pack/jobs_sample.jsonl \
    --index sample_jobs_v1 \
    --recreate
```

## 第三步：生成 sample 简历的 BM25 候选集

```bash
python scripts/retrieve_bm25_candidates.py \
    --input artifacts/dataset_iteration_05/sample_pack/candidate_profiles_sample.jsonl \
    --output artifacts/bm25/bm25_sample_top200.jsonl \
    --index sample_jobs_v1 \
    --size 50 \
    --source-type ""
```

> `--source-type ""` 不过滤来源类型（sample 岗位混合 enterprise / government）。

## 第四步：运行 text2vec 语义重排

```bash
python scripts/rerank_semantic_text2vec.py \
    --jobs artifacts/dataset_iteration_05/sample_pack/jobs_sample.jsonl \
    --bm25 artifacts/bm25/bm25_sample_top200.jsonl \
    --out-dir artifacts/semantic_text2vec \
    --max-jobs 10 \
    --limit 5
```
注意：如果不是第一次进行text2vec语义重排请在最后加上--force-encode，如果想要变换jods或者bm25对应文件只需要变换相应路径即可。

参数说明：

| 参数 | 值 | 说明 |
|------|-----|------|
| `--jobs` | `sample_pack/jobs_sample.jsonl` | 仅编码 sample 的 10 条岗位 |
| `--bm25` | `bm25_sample_top200.jsonl` | 5 条简历的 BM25 Top50 候选 |
| `--max-jobs 10` | 限制编码 10 条 | 避免全量编码（~5000+ 条消耗数十分钟） |
| `--limit 5` | 只处理前 5 条简历 | 快速验证链路逻辑 |
| `--force-encode` | 可选 | 若已有旧缓存（64d fallback）需加此参数覆盖 |

预期输出：

```text
[初始化] 模型信息: ..., "model_status": "loaded", ..., "embedding_dim": 768
[离线] 共 10 条岗位
[离线] 编码完成: (10, 768), 耗时 ~7s
[在线] 共 5 条查询
[在线] 完成 5 条查询, 250 个候选
```

## 第五步：运行评测对比（BM25 vs BM25 + text2vec）

```bash
python scripts/evaluate_semantic_rerank.py \
    --compare \
    --rankings \
        artifacts/bm25/bm25_sample_top200.jsonl:bm25_score:bm25_rank:BM25 \
        artifacts/semantic_text2vec/semantic_rerank_top200.jsonl:semantic_score:semantic_rank:text2vec \
    --labels artifacts/dataset_iteration_05/sample_pack/label_pairs_gold_sample.jsonl \
    --output artifacts/semantic_text2vec/sample_eval_report.json
```

输出报告：`artifacts/semantic_text2vec/sample_eval_report.json`

## 第六步（可选）：BGE-M3 对照组

```bash
python scripts/rerank_semantic_bge.py \
    --jobs artifacts/dataset_iteration_05/sample_pack/jobs_sample.jsonl \
    --bm25 artifacts/bm25/bm25_sample_top200.jsonl \
    --out-dir artifacts/semantic_bge \
    --max-jobs 10 \
    --limit 5
```

> BGE-M3 模型约 2.2 GB，首次加载更慢，低配置机器可跳过此步骤。

## 常见问题

### Q1: 输出 `embedding_dim: 64` 而不是 `768`

模型未正确加载（fallback 模式）。检查：
- Docker 容器是否能访问 Hugging Face / hf-mirror.com
- `~/.cache/huggingface/` 目录是否已挂载到容器

### Q2: `evaluated_queries: 1`

sample 数据中只有 5 条简历且有金标配对的更少，评测结果仅供参考（验证链路是否跑通），不作为模型效果判断依据。

### Q3: 想要更多样本但不等同于全量

将 `--limit` 从 5 调大到需要的值（例如 `--limit 50`），同时确保 BM25 候选集已覆盖对应数量的简历。
