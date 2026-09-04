# v2 岗位池运行时切换与真实前端链路实验流程

**交付对象**：算法组

**目的**：验证生产/演示环境是否真正使用 `canonical_role_pool_v2`，并从前端完成一次“简历上传 -> 三级岗位定位 -> 具体 JD 推荐 -> 能力差距分析 -> 图谱展示”的完整业务链路。

本实验不是重新训练模型，也不是重新设计匹配算法。除配置、数据路径和依赖 v2 输入的索引/图/向量产物外，不得修改 BM25、语义模型、KG 打分、Fusion 权重或核心匹配逻辑。

本文件不包含后端或前端单元测试覆盖率任务。覆盖率由项目侧单独完成，算法组不要重复执行该工作。

## 一、固定版本与执行原则

### 1. 使用的 v2 输入

```text
岗位 JD：artifacts/canonical_role_pool_v2/canonical_jobs.jsonl
岗位目录：artifacts/canonical_role_pool_v2/canonical_roles.csv
运行清单：artifacts/canonical_role_pool_v2/runtime_manifest.json
运行时目录：backend-src/app/data/canonical_role_pool/v2/
```

执行前核对 `runtime_manifest.json` 中的 SHA-256。当前预期值：

```text
canonical_jobs.jsonl
d95655a583b07e7f2a7f195db296f1aa3f40d4ce3ba35967a23ddb3e7a0a5c02

canonical_roles.csv
a2e07e9e21ff2857525e3ba4a2a23aa03d18a323d366af65de541396845d4f96
```

### 2. 不得破坏 v1

- v1 Elasticsearch 索引、Neo4j 图、向量和 Fusion 产物保持不变；
- v2 使用独立索引、独立图命名空间和独立产物目录；
- 任何失败都通过恢复配置并重启回滚，不删除 v2 或 v1 数据；
- 所有输出必须记录 `role_pool_version=v2`、输入哈希、Git 提交和执行时间。

## 二、实验 A：确认运行时默认已切换到 v2

### A-1. 记录执行环境

在算法组实际部署机器上记录：

```powershell
git rev-parse HEAD
Get-FileHash artifacts/canonical_role_pool_v2/canonical_jobs.jsonl -Algorithm SHA256
Get-FileHash artifacts/canonical_role_pool_v2/canonical_roles.csv -Algorithm SHA256
docker compose ps
```

如果不是 Docker 部署，记录实际进程启动命令、配置文件和服务版本。

### A-2. 写入实际服务配置

在算法组使用的 Docker Compose、进程管理器或 CI/CD 启动配置中设置，而不是只在临时 PowerShell 会话中设置：

```text
JOB_HUNT_CANONICAL_ROLE_POOL_PATH=/app/artifacts/canonical_role_pool_v2/canonical_jobs.jsonl
JOB_HUNT_CANONICAL_ROLE_DATA_DIR=/app/app/data/canonical_role_pool/v2
```

BM25、语义、KG、Fusion 的路径或索引名也必须指向 v2 对应产物，例如：

```text
canonical_jobs_v2
artifacts/role_pool_runtime/v2/production_bm25/
artifacts/role_pool_runtime/v2/production_semantic_bge/
artifacts/role_pool_runtime/v2/production_kg/
artifacts/role_pool_runtime/v2/production_fusion/
```

不要只切换 canonical role pool 文件而继续读取 v1 的 BM25、向量、KG 或 Fusion 结果。

### A-3. 重启并检查启动日志

```powershell
docker compose up -d
docker compose ps
docker compose logs backend --tail 300
```

启动日志中必须能找到以下信息，或通过等价的健康检查接口返回：

```text
role_pool_version=v2
canonical role pool path=...canonical_role_pool_v2/canonical_jobs.jsonl
canonical role data dir=.../canonical_role_pool/v2
BM25 index=canonical_jobs_v2
```

如果当前服务没有打印这些信息，请增加启动时只读诊断日志；不要修改评分逻辑。

### A-4. 做运行时数据一致性检查

至少检查以下数量和约束：

| 检查项 | 预期 |
|---|---:|
| v2 mapped JD | 11,361 |
| v2 激活三级岗位目录 | 76 |
| review queue | 2,161，不能进入正式候选 |
| Elasticsearch v2 文档 | 11,361 |
| Fusion 候选中的 v1 job_id | 0 |
| 同一请求跨 BM25/语义/KG/Fusion 的 query_id | 完全一致 |
| 同一候选跨阶段的 job_id | 完全一致 |

同时抽查至少 10 条候选 JD，确认：

- `job_id` 能在 v2 `canonical_jobs.jsonl` 找到；
- `canonical_role_id` 能在 v2 `canonical_roles.csv` 找到；
- 三级岗位名称、JD 标题和技能字段没有被 v1 数据覆盖；
- review-only 或未映射记录没有进入正式匹配闭集。

### A-5. 实验 A 的交付物

算法组需提交以下文件或等价内容：

```text
v2_runtime_switch_report.json
v2_startup.log
v2_runtime_consistency.log
v2_config_snapshot.txt
```

`v2_runtime_switch_report.json` 至少包含：

```json
{
  "role_pool_version": "v2",
  "git_commit": "...",
  "jobs_sha256": "...",
  "roles_sha256": "...",
  "es_index": "canonical_jobs_v2",
  "es_document_count": 11361,
  "active_role_count": 76,
  "review_queue_count": 2161,
  "v1_job_ids_in_runtime_results": 0,
  "status": "passed"
}
```

### A-6. 实验 A 通过标准

只有以下条件全部满足，才能说“运行时默认已切换到 v2”：

1. 服务启动配置永久指向 v2，而非临时环境变量；
2. 启动日志或诊断接口明确显示 `role_pool_version=v2`；
3. BM25、语义、KG、Fusion 均使用 v2 产物；
4. 候选中没有 v1 `job_id` 或 review-only 记录；
5. 输入哈希与 `runtime_manifest.json` 一致；
6. v1 可以通过恢复原配置正常回滚。

## 三、实验 B：真实前端端到端业务演示

### B-1. 测试样本

准备 3 至 5 份脱敏简历，至少覆盖：

- 一个技术研发岗位；
- 一个产品或项目管理岗位；
- 一个 UI/UX、安全合规或其他新增方向岗位。

每份简历记录 `test_resume_id`、文件 SHA-256、来源类型和是否脱敏。不得使用系统自动生成的推荐结果作为人工答案。

### B-2. 前端操作

在真实前端页面执行：

1. 打开简历上传/诊断页面；
2. 上传脱敏 PDF 或 Word 简历；
3. 等待解析和推荐完成；
4. 记录三级岗位、具体 JD、匹配分数、命中技能和缺失技能；
5. 打开岗位能力图谱，确认岗位节点、技能节点和关系可展示；
6. 保存浏览器截图和请求网络日志。

### B-3. 后端链路检查

前端操作期间，确认实际请求依次完成。当前仓库的典型接口为：

```text
POST /api/v1/jobs/upload-resume
POST /api/v1/bm25/search
POST /api/v1/semantic/rerank
POST /api/v1/kg/analyze
POST /api/v1/fusion/rank 或 /api/v1/fusion/recommend
GET  /api/v1/graph
```

如果当前版本采用稳定诊断接口，也检查：

```text
POST /api/v1/diagnosis/analyze
```

每一步记录 HTTP 状态、耗时、`query_id`、候选数量和是否使用 fallback。接口路径以当前部署版本实际 OpenAPI 为准，但不得跳过其中任一业务阶段。

### B-4. 每份简历必须核对的结果

| 项目 | 核对要求 |
|---|---|
| 解析 | 返回非空简历文本、技能和经历信息 |
| 三级岗位 | 返回 `canonical_role_id`，且存在于 v2 岗位目录 |
| 具体 JD | 返回真实 JD 标题、`job_id` 和所属三级岗位 |
| 岗位一致性 | 推荐 JD 的 `canonical_role_id` 与岗位定位结果一致 |
| 技能证据 | 有命中技能、缺失技能或对应证据，不得只有一个黑盒分数 |
| KG 差距 | `skill_coverage`、缺失技能或图关系不能全部为空/为零 |
| 图谱 | 节点和边来自 v2，不能是 mock 数据或 v1 岗位 |
| 降级状态 | 页面和 API 不得显示 `fallback`、`mock`、`degraded`，除非明确记录为失败 |
| 版本 | 每一步都能追溯到 `role_pool_version=v2` |

### B-5. 重点防回归检查

旧链路曾出现过以下问题，本次必须逐项排除：

- BM25 返回的 `job_id` 与 Neo4j 岗位 ID 不一致；
- KG 接口虽然 HTTP 200，但 `skill_coverage=0`、缺失技能为空；
- Fusion 返回旧岗位库结果；
- 图谱页面显示 mock 数据或固定增长值；
- 前端展示的三级岗位与推荐 JD 所属岗位不一致；
- 真实请求失败后静默切换到旧推荐接口。

### B-6. 实验 B 的交付物

每份简历至少提交：

```text
e2e_<test_resume_id>_frontend.png
e2e_<test_resume_id>_network.har 或等价 API 日志
e2e_<test_resume_id>_result.json
```

另提交汇总文件：

```text
v2_frontend_e2e_report.json
v2_frontend_e2e_summary.md
```

汇总 JSON 至少包含：

```json
{
  "role_pool_version": "v2",
  "sample_count": 5,
  "all_requests_http_2xx": true,
  "fallback_count": 0,
  "mock_graph_count": 0,
  "v1_job_id_count": 0,
  "nonempty_kg_gap_count": 5,
  "consistent_canonical_role_count": 5,
  "status": "passed"
}
```

### B-7. 实验 B 通过标准

对全部样本同时满足以下条件，才可说“真实前端端到端链路已打通”：

1. 前端上传成功并得到解析结果；
2. 三级岗位、具体 JD、技能证据和图谱结果均来自 v2；
3. BM25 -> 语义 -> KG -> Fusion 的 `query_id/job_id` 可追踪；
4. KG 差距分析返回有意义的技能覆盖或缺失技能；
5. 图谱不是 mock/fallback，且岗位节点和技能边存在；
6. 没有静默降级到旧岗位库；
7. 至少一份新增非技术岗位样本成功走完整链路。

## 四、算法组回传格式

请一次性回传：

1. 实验 A 的配置快照、启动日志、运行时一致性报告；
2. 实验 B 每份简历的截图、API/网络日志和结构化结果；
3. v2 输入哈希、Git 提交、ES 文档数、Neo4j 节点/关系数；
4. 明确列出任何 fallback、mock、空 KG、v1 ID 或失败请求；
5. 对每个失败项说明是配置、数据、索引、图导入、接口接线还是前端展示问题；
6. 最终给出 `passed` 或 `failed`，不能只给“基本完成”。

本实验通过后，才可以把“算法组环境已经切换并完成真实业务链路验证”写入赛题技术报告。它仍然不等同于独立人工金标上的 90% 泛化准确率，准确率必须由冻结评测集单独报告。

算法组只需完成本文件中的实验 A、实验 B，并将配置快照、启动日志、API/网络日志、前端截图和结构化 JSON 报告回传项目负责人。项目负责人再将结果交由 Codex 复核。
