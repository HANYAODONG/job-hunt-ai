# Workflow Artifacts

This directory is for locally generated workflow outputs. The repository tracks this README only; generated data files stay local by default.

Recommended module layout:

| Directory | Owner workflow | Purpose | Typical files |
| --- | --- | --- | --- |
| `dataset_iteration_05/` | Workflow 1, data foundation | Normalized jobs, resumes, labels, and evaluation inputs | `jobs.jsonl`, `candidate_profiles.jsonl`, `label_pairs_gold.jsonl`, `label_pairs_silver.jsonl`, `data_quality_report.json` |
| `bm25/` | Workflow 5, lexical retrieval | BM25 candidate recall output for downstream reranking | `bm25_top200.jsonl` |
| `semantic_index/` | Workflow 2, BGE semantic reranking | Job embedding index and semantic rerank output | `jobs_embeddings.npy`, `jobs_embedding_ids.json`, `semantic_rerank_output.jsonl` |
| `kg/` | Workflow 3, knowledge graph | KG import, path, and graph feature outputs | `kg_import_report.json`, `kg_features.jsonl` |
| `fusion/` | Workflow 4, fusion ranking | Final fused ranking, explanations, and UI demo inputs | `fusion_rankings.jsonl`, `fusion_explanations.jsonl` |

Dependency direction:

1. `dataset_iteration_05/` is the shared input contract.
2. `bm25/`, `semantic_index/`, and `kg/` read the normalized data and write their own outputs.
3. `fusion/` reads BM25, BGE, and KG outputs, then produces final ranking and explanations.

Do not let one workflow overwrite another workflow's directory. If a file is only for testing, put it under that module's own subdirectory and name it clearly, for example `semantic_index/sample/`.
