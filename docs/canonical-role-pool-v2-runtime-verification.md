# Canonical Role Pool v2重建与回归记录

## 1. 本次结论

Demo分支交付的v2岗位池已完成真实服务重建和回归验证。v2继续保持隔离接入，不覆盖v1默认运行数据；组长可先拉取`main`进行对照测试，确认后再通过环境变量切换。

## 2. 已完成的重建

| 环节 | 结果 |
| --- | --- |
| v2规范岗位池 | 11,361条JD，`job_id`无重复 |
| Elasticsearch | 独立索引`canonical_jobs_v2`，文档数11,361 |
| BGE-M3 | `BAAI/bge-m3`，CUDA实跑，11,361×1,024维，编码耗时1,134.4秒 |
| Neo4j隔离图 | 11,361个`V2Job`、74个`V2CanonicalRole`、24,415个`V2Skill` |
| 图关系 | 11,361条`INSTANCE_OF`、143,222条`REQUIRES_SKILL` |
| 冻结回归集 | 400份简历，BM25 Top-200，共80,000个候选对 |
| Fusion | 四套既有预设均完成，查询数和候选对跨阶段完全一致 |
| 岗位优先输出 | 400份简历均生成三级岗位优先、岗位内JD排序结果 |

v2 JD的LF归一化SHA-256为：

```text
d95655a583b07e7f2a7f195db296f1aa3f40d4ce3ba35967a23ddb3e7a0a5c02
```

Windows检出文件可能使用CRLF，直接运行`Get-FileHash`会得到不同值；校验脚本会统一换行后再计算，避免把换行差异误判为数据变化。

## 3. 已完成的测试

- 后端完整测试：128项通过（包含新增运行脚本测试4项）。
- v2专项测试：33项通过。
- 前端测试：4个测试套件、15项测试通过。
- 接口冒烟：`/health`、前端首页和`/api/v1/fusion/role-aware-rank`均返回成功。
- 跨阶段一致性：BM25、BGE-M3、KG、Fusion均为400个相同`query_id`和80,000个相同`query_id/job_id`候选对，未混入v1岗位ID。

这里的400份简历是冻结回归集，用于验证岗位池切换没有破坏全链路；11,361条岗位向量、ES索引和Neo4j图均为全量重建。没有把30,200份简历全部离线预计算，因为线上检索按请求生成候选，全量预计算不是接口可用和准确率验收的前置条件。

## 4. 组长拉取后的快速测试

在仓库根目录执行：

```powershell
git switch main
git pull origin main
docker compose up -d --build
docker compose ps
```

访问：

- 前端：`http://localhost:18080`
- 后端文档：`http://localhost:18088/docs`
- Elasticsearch：`http://localhost:9200`
- Neo4j：`http://localhost:7474`，用户名`neo4j`，密码`password`

运行代码回归：

```powershell
docker compose exec backend pytest tests -q --disable-warnings
docker compose exec frontend npm test -- --watchAll=false
```

若本机保留了重建产物，可执行跨阶段一致性校验：

```powershell
docker compose exec backend python scripts/validate_role_pool_v2_runtime.py `
  --jobs /app/artifacts/canonical_role_pool_v2/canonical_jobs.jsonl `
  --bm25 /app/artifacts/role_pool_runtime/v2/production_bm25_smoke/bm25_top200.jsonl `
  --semantic /app/artifacts/role_pool_runtime/v2/production_semantic_bge/semantic_rerank_top200.jsonl `
  --kg /app/artifacts/role_pool_runtime/v2/production_kg/kg_features.jsonl `
  --fusion /app/artifacts/role_pool_runtime/v2/production_fusion/fusion_full.jsonl
```

## 5. v2切换方式

本次合并不会自动替换v1。确认回归结果后，在实际服务启动环境中设置：

```text
JOB_HUNT_CANONICAL_ROLE_POOL_PATH=/app/artifacts/canonical_role_pool_v2/canonical_jobs.jsonl
JOB_HUNT_CANONICAL_ROLE_DATA_DIR=/app/app/data/canonical_role_pool/v2
```

路径应按部署环境调整。移除这两个变量并重启服务即可回滚v1。
