# 岗位池 v2 本地重建与切换说明

## 版本与边界

- 岗位池版本：`canonical_role_pool_v2`
- 可用 JD：11,361 条
- 激活三级岗位：76 个
- v1 未被覆盖；所有 v2 产物位于 `artifacts/role_pool_runtime/v2/`。

本次只更换岗位池输入和重建其依赖产物，未修改 BM25 参数、语义模型选择、Fusion 分层权重、知识图谱评分公式或人岗匹配核心算法。

## 已完成的本地工作

| 产物 | 路径 | 说明 |
| --- | --- | --- |
| 运行时清单 | `artifacts/canonical_role_pool_v2/runtime_manifest.json` | 固化岗位池路径、角色目录、SHA-256 和环境变量。 |
| 本地 BM25 索引 | `artifacts/role_pool_runtime/v2/local_rebuild/local_bm25/` | 标准 BM25 公式 `k1=1.2, b=0.75` 的本地稀疏索引、词表与 400 份评测简历 Top-200 候选。 |
| 本地语义索引 | `artifacts/role_pool_runtime/v2/local_rebuild/semantic/` | 项目既有 768 维 char n-gram 哈希回退向量及 Top-200 候选。 |
| KG 导入包 | `artifacts/role_pool_runtime/v2/local_rebuild/kg_import/` | 11,361 个岗位节点、74 个有 JD 覆盖的角色节点、24,415 个技能节点、154,583 条关系。 |
| KG 特征 | `artifacts/role_pool_runtime/v2/local_rebuild/kg_features/kg_features.jsonl` | 对候选集使用既有技能覆盖率和 Jaccard 关联度公式生成。 |
| Fusion 结果 | `artifacts/role_pool_runtime/v2/local_rebuild/fusion/` | 原 `run_fusion_pipeline.py` 输出的四组权重消融结果。 |
| 角色感知结果 | `artifacts/role_pool_runtime/v2/local_rebuild/role_aware/recommendations.jsonl` | 先选择 canonical L3，再展示该岗位内 JD 的结果。 |

本地重建范围为现有 400 份评测简历，避免对 30,200 份简历进行 11,361 条 JD 的无必要全量两两离线排序。重建脚本可通过 `--cases` 和 `--profiles` 切换至全量。

## 回归结果

使用原有两阶段评测脚本、原有 400 份金标和原有技能评分，仅替换为 v2 JD 与 v2 岗位映射：

| 指标 | v1 | v2 |
| --- | ---: | ---: |
| 三级岗位 Top-1 | 99.75% | 99.75% |
| 具体 JD Top-2 | 91.50% | 91.50% |
| 具体 JD Top-3 | 95.75% | 95.75% |

因此，岗位池扩充没有使既有技术岗位评测集退化。

## 本地回退产物的解释

本机没有 Elasticsearch、Neo4j，也没有 `sentence-transformers`。本地 BM25 使用 char n-gram 分词近似，语义使用项目已有的哈希向量回退器。它们验证了数据、接口和融合链路，不应替代生产服务产物，也不应以此重新宣称比赛准确率。

接入 Elasticsearch 后，应以相同 v2 JD 在一个新索引（例如 `canonical_jobs_v2`）中运行项目原 `ChineseBM25Service`。接入 Neo4j 后，应导入 `kg_import/` 中的节点与关系到一个新库或新标签。旧索引和旧图库保持不动。

## 切换与回滚

在正式环境确认服务产物后，设置：

```powershell
$env:JOB_HUNT_CANONICAL_ROLE_POOL_PATH = "D:\job-hunt\artifacts\canonical_role_pool_v2\canonical_jobs.jsonl"
$env:JOB_HUNT_CANONICAL_ROLE_DATA_DIR = "D:\job-hunt\backend-src\app\data\canonical_role_pool\v2"
```

移除这两个环境变量即可回到 v1 默认路径。不要删除 v1 文件、旧 Elasticsearch 索引或旧 Neo4j 图数据。
