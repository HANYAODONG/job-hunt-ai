# Workflow Artifacts

This directory is for locally generated workflow outputs. The repository tracks this README only; generated data files stay local by default.

Recommended module layout:

| Directory | Owner workflow | Purpose | Typical files |
| --- | --- | --- | --- |
| `dataset_iteration_05/` | Workflow 1, data foundation | Normalized jobs, resumes, labels, and evaluation inputs | `jobs.jsonl`, `candidate_profiles.jsonl`, `label_pairs_gold.jsonl`, `label_pairs_silver.jsonl`, `data_quality_report.json` |
| `bm25/` | Workflow 5, lexical retrieval | BM25 candidate recall output for downstream reranking | `bm25_top200.jsonl` |
| `semantic_text2vec/` | Workflow 2, lightweight semantic reranking | text2vec embedding index and semantic rerank output | `jobs_embeddings.npy`, `jobs_embedding_ids.json`, `semantic_rerank_top200.jsonl` |
| `semantic_bge/` | Workflow 2, BGE semantic reranking | BGE embedding index and semantic rerank output | `jobs_embeddings.npy`, `jobs_embedding_ids.json`, `semantic_rerank_top200.jsonl` |
| `skill_graph/` | Workflow 3, skill extraction and KG | KG import, path, and graph feature outputs | `kg_import_report.json`, `kg_features.jsonl`, `skill_features.jsonl` |
| `fusion_ranking/` | Workflow 4, fusion ranking | Final fused ranking, explanations, and UI demo inputs | `fusion_rankings.jsonl`, `fusion_explanations.jsonl` |
| `evaluation/` | Workflow 1, evaluation | Shared evaluation reports | `baseline_eval_report.json`, `fusion_eval_report.json` |

Dependency direction:

1. `dataset_iteration_05/` is the shared input contract.
2. `bm25/`, `semantic_text2vec/`, `semantic_bge/`, and `skill_graph/` read the normalized data and write their own outputs.
3. `fusion_ranking/` reads BM25, semantic rerank, and KG outputs, then produces final ranking and explanations.
4. `evaluation/` stores reproducible metric reports.

Do not let one workflow overwrite another workflow's directory. If a file is only for testing, put it under that module's own subdirectory and name it clearly, for example `semantic_text2vec/sample/`.