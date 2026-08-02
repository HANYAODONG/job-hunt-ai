# 算法与大模型组代码协作约定

## 目标

当前项目由多个工作流并行推进。为了减少合并冲突、避免不同模块互相覆盖，后续代码提交尽量遵循“各自新增、少改公共文件、输入输出清晰”的原则。

## 目录分工

### 后端功能代码

主要修改区域：

```text
backend-src/app/
```

各工作流优先在以下目录新增或修改自己的模块：

```text
backend-src/app/services/
backend-src/app/api/endpoints/
backend-src/app/models/
```

例如：

- BM25 召回服务放在 `backend-src/app/services/`。
- BGE 语义重排服务放在 `backend-src/app/services/`。
- 知识图谱分析接口放在 `backend-src/app/api/endpoints/`。
- 融合排序模型放在 `backend-src/app/models/`。

### 脚本

额外的数据处理、索引构建、批量生成、评估脚本统一放在：

```text
scripts/
backend-src/scripts/
```

约定：

- 项目通用脚本放 `scripts/`。
- 强依赖后端代码或后端服务的脚本放 `backend-src/scripts/`。

## 数据与结果

### 数据集

原始数据、外部数据、小组提供的数据统一放在：

```text
dataset/
```

大文件原则上不提交到 GitHub，只提交 README、字段说明或处理脚本。

### 结果输出

各工作流生成的中间结果、向量、排序结果、评估报告统一输出到：

```text
artifacts/
```

建议按工作流拆分子目录：

```text
artifacts/dataset_iteration_05/
artifacts/bm25/
artifacts/semantic_index/
artifacts/kg/
artifacts/fusion/
```

## 上下游关系

各工作流可以读取上游结果，但不要覆盖上游脚本和输出格式。

例如 BGE 工作流可以读取：

```text
artifacts/dataset_iteration_05/jobs.jsonl
artifacts/dataset_iteration_05/candidate_profiles.jsonl
artifacts/bm25/bm25_top200.jsonl
```

然后输出自己的结果：

```text
artifacts/semantic_index/jobs_embeddings.npy
artifacts/semantic_index/jobs_embedding_ids.json
artifacts/semantic_index/semantic_rerank_output.jsonl
```

不要反向修改：

```text
scripts/dataset_adapter.py
scripts/evaluate_candidate_rankings.py
artifacts/dataset_iteration_05/ 的字段结构
artifacts/bm25/ 的输出结构
```

如果确实发现上游字段设计有问题，先在群里说明，由组内统一修改 schema。

## 公共文件修改规则

以下文件容易产生冲突，修改前最好先说明原因：

```text
backend-src/app/main.py
scripts/dataset_adapter.py
scripts/evaluate_candidate_rankings.py
docs/data-schema.md
docker-compose.yml
.gitignore
```

如果必须修改公共文件，只做必要改动，不要覆盖已有内容。

例如 `backend-src/app/main.py` 中新增路由时，应保留已有路由：

```python
app.include_router(bm25_router, prefix="/api/v1/bm25", tags=["chinese-bm25"])
app.include_router(kg_analysis_router, prefix="/api/v1/kg", tags=["knowledge_graph"])
app.include_router(semantic_embedding_router, prefix="/api/v1/semantic", tags=["semantic"])
app.include_router(fusion_router, prefix="/api/v1/fusion", tags=["fusion"])
```

## PR 提交原则

每个 PR 尽量做到：

- 只新增自己模块需要的文件。
- 少量修改公共入口。
- 不删除已有文件。
- 不提交本地临时脚本。
- 不提交数据大文件、模型文件、缓存文件。
- 输出格式和文档说明保持一致。

如果产生冲突，优先保留 `main` 分支已有内容，再把自己新增的功能合进去。

## 本地测试数据

本地电脑跑不动全量数据是正常的，可以使用小样本或 limit 参数测试。

允许使用：

```text
artifacts/dataset_iteration_05/sample_pack/
```

或者脚本参数：

```powershell
--limit
--jobs-limit
--candidates-limit
--top-k
```

要求：

- 小样本测试可以少跑数据。
- 输出字段必须和全量输出一致。
- 后续统一联调时再切换到全量数据。

## 一句话总结

数据放 `dataset/`，结果放 `artifacts/`，脚本放 `scripts/` 或 `backend-src/scripts/`，后端模块放 `backend-src/app/`。公共文件少改、不覆盖、不删除。
