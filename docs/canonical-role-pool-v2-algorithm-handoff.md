# 岗位池 v2 算法组交接与接入报告

**交接版本**：`canonical_role_pool_v2`  
**状态**：已构建并完成本地链路验证，尚未设为运行时默认岗位池  
**交接目标**：在不改写现有 BM25、语义检索、Fusion、KG 打分和人岗匹配核心算法的前提下，将它们的输入切换为岗位池 v2，并重新生成依赖旧 JD 的服务产物。

## 1. 结论与边界

本次工作完成的是岗位池数据层、岗位目录层和本地可运行产物的增量建设。算法组不需要为了接入 v2 重写核心算法；需要做的是在隔离的 v2 命名空间中，以新的 JD 和岗位目录重新建立索引、向量、图数据和融合候选，并做同集回归后切换配置。

岗位池的职责是统一“岗位分类空间”，不是替代具体 JD 匹配：

```text
简历
  -> 三级功能岗位（canonical_role_id）
  -> 该岗位内或该岗位优先的真实 JD 候选
  -> 按技能、经验、学历、地点等原有规则排序
  -> 返回具体 JD + 所属三级标准岗位
```

例如 `Java 后端开发工程师`、`Go 服务端工程师`、`Python 后端开发工程师` 是不同的真实 JD 标题和技术栈要求，但统一落在三级岗位 `后端开发工程师`。语言信息保留在 `title`、`required_skills` 和 `role_specialization`，继续影响具体 JD 排序，不能被三级岗位归并抹平。

v1 没有被删除或覆盖。生产接入必须新建 v2 索引/图数据/产物目录，验收通过后才修改运行时环境变量。

## 2. 已完成交付

### 2.1 岗位池和目录

| 项目 | 路径 | 已验证内容 |
| --- | --- | --- |
| v2 规范 JD | `artifacts/canonical_role_pool_v2/canonical_jobs.jsonl` | 11,361 条 `mapped` JD；每条保留真实标题、来源字段、技能和 `canonical_role_id`。 |
| v2 岗位目录 | `artifacts/canonical_role_pool_v2/canonical_roles.csv` | 76 个激活的三级功能岗位；岗位名、一级/二级归属、定义和边界均在目录中。 |
| v2 运行时目录 | `backend-src/app/data/canonical_role_pool/v2/` | 角色目录、来源映射、标题/技能细化规则、相邻岗位关系。 |
| 版本清单 | `artifacts/canonical_role_pool_v2/runtime_manifest.json` | 固化版本、绝对路径、文件哈希和运行时变量。 |
| 审核队列 | 岗位池 v2 构建产物中的 review records | 2,161 条不确定、未映射或跨域记录不进入正式匹配闭集。 |

本轮新增并激活了产品、项目/交付、UI/UX 与安全合规等此前覆盖不足的现实岗位方向，包括：产品经理、数据产品经理、技术产品经理、安全合规工程师、研发项目经理、游戏项目经理、交付项目经理、IT 项目经理、UI/UX 设计师。

### 2.2 版本完整性

以下值来自 `runtime_manifest.json`，生产重建前请先验证；若不同，须重新确认输入版本而不是混合使用产物。

| 文件 | SHA-256 |
| --- | --- |
| `canonical_jobs.jsonl` | `d95655a583b07e7f2a7f195db296f1aa3f40d4ce3ba35967a23ddb3e7a0a5c02` |
| `canonical_roles.csv` | `a2e07e9e21ff2857525e3ba4a2a23aa03d18a323d366af65de541396845d4f96` |

PowerShell 核验：

```powershell
Get-FileHash artifacts/canonical_role_pool_v2/canonical_jobs.jsonl -Algorithm SHA256
Get-FileHash backend-src/app/data/canonical_role_pool/v2/canonical_roles.csv -Algorithm SHA256
Get-Content artifacts/canonical_role_pool_v2/runtime_manifest.json
```

### 2.3 已完成的本地重建

本机缺少 Elasticsearch、Neo4j 和 `sentence-transformers`，因此本地生成的是可复现的数据/接口验证产物，不是生产服务产物。

| 产物 | 位置 | 范围与用途 |
| --- | --- | --- |
| 本地 BM25 | `artifacts/role_pool_runtime/v2/local_rebuild/local_bm25/` | 400 份评测简历、每份 Top-200；标准 BM25 公式 `k1=1.2, b=0.75`，但采用 char n-gram 分词。 |
| 本地语义结果 | `artifacts/role_pool_runtime/v2/local_rebuild/semantic/` | 768 维 char n-gram 哈希回退向量和 Top-200，验证文件接口。 |
| 图导入包 | `artifacts/role_pool_runtime/v2/local_rebuild/kg_import/` | 11,361 Job、74 个有 JD 覆盖的 CanonicalRole、24,415 Skill、154,583 条关系。76 个激活岗位中有 2 个暂未观察到可用 JD，故图中角色节点数为 74。 |
| 本地图特征 | `artifacts/role_pool_runtime/v2/local_rebuild/kg_features/kg_features.jsonl` | 130,958 个候选对，沿用技能覆盖率和 Jaccard 关联度公式。 |
| Fusion 消融 | `artifacts/role_pool_runtime/v2/local_rebuild/fusion/` | 原 `run_fusion_pipeline.py` 的四套既有权重输出。 |
| 岗位优先输出 | `artifacts/role_pool_runtime/v2/local_rebuild/role_aware/recommendations.jsonl` | 不更改 Fusion 分数，只将 JD 元数据接回并按 canonical L3 输出。 |

完整运行记录在 `artifacts/role_pool_runtime/v2/local_rebuild/local_rebuild_report.json`。这些文件可用于检查 schema、字段和跨模块兼容性，**不得**代替 Elasticsearch/BGE-M3/Neo4j 产物参与生产指标宣称。

### 2.4 已完成的代码兼容性改造

1. `backend-src/app/services/canonical_role_pool.py` 已支持环境变量 `JOB_HUNT_CANONICAL_ROLE_DATA_DIR`；变量未设置时仍默认读取 v1。
2. 运行时 JD 输入已有 `JOB_HUNT_CANONICAL_ROLE_POOL_PATH` 支持。
3. `backend-src/scripts/generate_semantic_artifacts.py` 已可显式传入 `--jobs`、`--profiles`、`--output-dir`，同时保留旧默认行为。
4. 已补充 v2 构建、运行时准备、本地重建、角色感知结果物化脚本，分别位于 `scripts/`。
5. `backend-src/tests/test_canonical_role_pool.py` 已通过 12 项测试；覆盖语言型后端岗位归并、未映射岗位拦截、标题/技能细化、相邻岗位计分和跨域标题检查。

上述改动不改变 BM25 参数、语义模型选择、Fusion 权重、KG 评分公式或核心人岗匹配算法。

## 3. 已有回归证据及其适用范围

使用原有两阶段评测器、原有 400 份金标和原有技能评分，仅将输入 JD/岗位映射替换为 v2 后得到：

| 指标 | 结果 |
| --- | ---: |
| 三级岗位 Top-1 | 99.75% |
| 已接受具体 JD Top-2 召回 | 91.50% |
| 已接受具体 JD Top-3 召回 | 95.75% |
| 已接受具体 JD Top-1 召回 | 86.25% |

结果文件：`artifacts/canonical_matching_eval_v2_400/manifest.json`、`case_metrics.csv`、`job_rankings_topk.csv`、`role_rankings.csv`。

评测单位是简历样本：先预测三级岗位，再只在该岗位内对具体 JD 排序。由于同一简历可能有多个人工认可的、标题归一后相同或相近的真实 JD，正式的“候选推荐命中”指标以 `accepted JD Recall@2/Recall@3` 为主；`Top-1` 作为更严格的辅助指标。

这组 400 条主要覆盖既有技术岗位，且与训练画像属于同一合成数据族。因此它只能证明 **v2 没有使原技术岗位评测退化、两阶段闭环可运行**，不能证明现实泛化能力，更不能单独作为赛题最终的 90% 人岗匹配正确率依据。产品、UI/UX、项目经理、安全合规等新增岗位需要补充独立的人工金标后再做覆盖性结论。

## 4. 算法组必须完成的生产重建

### 4.1 执行前约束

1. 使用 Python 3.10 或更高版本。当前 Windows 系统自带 Python 3.9，部分后端类型注解不兼容；本机可用 Python 3.11：`C:\Users\糊涂涂\AppData\Local\Programs\Python\Python311\python.exe`。
2. 保持 v1 Elasticsearch 索引、Neo4j 图和既有产物不动。所有 v2 输出写入 `artifacts/role_pool_runtime/v2/production_*`。
3. 同一批候选简历在 BM25、语义、KG、Fusion 中必须使用相同的 `query_id` 和 `job_id`，并记录 v2 JD 哈希。
4. 先沿用现有模型和 Fusion 默认权重。模型/权重优化属于可选实验，不得与“岗位池版本切换”混在一次变更中。

示例变量（在仓库根目录执行）：

```powershell
$python = 'C:\Users\糊涂涂\AppData\Local\Programs\Python\Python311\python.exe'
$jobs = 'artifacts/canonical_role_pool_v2/canonical_jobs.jsonl'
$profiles = 'artifacts/dataset_iteration_05/candidate_profiles.jsonl'
$runtime = 'artifacts/role_pool_runtime/v2'
```

### 4.2 必做 1：建立隔离的 Elasticsearch v2 索引

启动 Elasticsearch 后，使用新索引名，例如 `canonical_jobs_v2`。不要对 v1 索引执行 `--recreate`。

```powershell
& $python backend-src/scripts/index_chinese_jobs.py `
  --input $jobs `
  --index canonical_jobs_v2 `
  --recreate
```

随后以项目真实 `ChineseBM25Service` 生成 Top-200 候选：

```powershell
New-Item -ItemType Directory -Force "$runtime/production_bm25" | Out-Null
& $python backend-src/scripts/retrieve_bm25_candidates.py `
  --input $profiles `
  --output "$runtime/production_bm25/bm25_top200.jsonl" `
  --index canonical_jobs_v2 `
  --size 200 `
  --source-type enterprise
```

验收：输出 JSONL 每个 `query_id` 有不超过 200 个候选；候选 `job_id` 全部存在于 v2 `canonical_jobs.jsonl`；记录 ES 索引的 document count 与 11,361 条 mapped JD 的差异和原因。

### 4.3 必做 2：按既有生产语义模型重建岗位向量和重排结果

在 BGE-M3 与 text2vec 中选择算法组当前线上实际使用的 **一个** 模型，不能把两套结果混用。若线上使用 BGE-M3，示例为：

```powershell
New-Item -ItemType Directory -Force "$runtime/production_semantic_bge" | Out-Null
& $python backend-src/scripts/rerank_semantic_bge.py `
  --jobs $jobs `
  --bm25 "$runtime/production_bm25/bm25_top200.jsonl" `
  --out-dir "$runtime/production_semantic_bge" `
  --device cuda `
  --force-encode
```

其预期主要输出为：

```text
artifacts/role_pool_runtime/v2/production_semantic_bge/jobs_embeddings.npy
artifacts/role_pool_runtime/v2/production_semantic_bge/semantic_rerank_top200.jsonl
artifacts/role_pool_runtime/v2/production_semantic_bge/run_metadata.json
```

无 GPU 时可改为 `--device cpu`，但不应改用本地哈希回退产物替代已确定的生产模型。运行元数据需记录模型名、批大小、设备和 v2 JD 哈希。

### 4.4 必做 3：导入隔离的 Neo4j v2 图，并生成真实 KG 特征

交付了较完整的 v2 图导入包：

```text
artifacts/role_pool_runtime/v2/local_rebuild/kg_import/canonical_roles.jsonl
artifacts/role_pool_runtime/v2/local_rebuild/kg_import/jobs.jsonl
artifacts/role_pool_runtime/v2/local_rebuild/kg_import/skills.jsonl
artifacts/role_pool_runtime/v2/local_rebuild/kg_import/relationships.jsonl
```

图结构至少应包含：

```text
(:Job {id, title, canonical_role_id, ...})
(:CanonicalRole {canonical_role_id, role_name, domain, direction})
(:Skill {skill_id, skill_name})
(:Job)-[:INSTANCE_OF]->(:CanonicalRole)
(:Job)-[:REQUIRES_SKILL]->(:Skill)
```

现有 `backend-src/scripts/import_canonical_graph.py` 可先将 Job-Skill 基础图导入隔离 Neo4j，但它目前不会读取 `CanonicalRole` 节点和 `INSTANCE_OF` 关系。因此，算法组需在 **导入/ETL 层** 补齐上述两类节点/边，或按该包使用批量 Cypher 导入；这是数据接入工作，不涉及修改 KG 打分算法。基础导入命令为：

```powershell
& $python backend-src/scripts/import_canonical_graph.py `
  --jobs $jobs `
  --uri bolt://localhost:7687 `
  --user neo4j `
  --password <Neo4jPassword>
```

隔离方式任选其一，但必须可回滚：新 Neo4j database、v2 专用标签，或所有节点增加 `role_pool_version: 'v2'` 并在查询中强制过滤。不得与 v1 节点直接混写后再靠模糊查询区分。

然后针对 **与 4.2 相同的 BM25/语义候选对** 生成 KG 特征，写到：

```text
artifacts/role_pool_runtime/v2/production_kg/kg_features.jsonl
```

KG 特征文件的每行至少包含 `query_id`、`job_id`、`skill_coverage`、`job_family_match`、`graph_relatedness`，并保持现有 `run_fusion_pipeline.py` 所使用的字段命名。现仓库未提供一个直接连 Neo4j、批量输出该文件的独立 CLI；算法组应复用其现有服务/特征提取路径，或将本地重建脚本中的既有技能覆盖率和 Jaccard 字段逻辑移入该路径。无论采取哪一种，先保持现有特征定义，另开任务再讨论算法优化。

### 4.5 必做 4：用原 Fusion 配置融合 v2 候选

先运行四个既有预设以便回归比较，随后将当前线上采用的预设作为候选默认：

```powershell
New-Item -ItemType Directory -Force "$runtime/production_fusion" | Out-Null
& $python backend-src/scripts/run_fusion_pipeline.py `
  --bm25-input "$runtime/production_bm25/bm25_top200.jsonl" `
  --semantic-input "$runtime/production_semantic_bge/semantic_rerank_top200.jsonl" `
  --kg-input "$runtime/production_kg/kg_features.jsonl" `
  --output-dir "$runtime/production_fusion" `
  --preset all `
  --top-k 200
```

若线上使用 text2vec，只将 `--semantic-input` 改成对应 `production_semantic_text2vec/semantic_rerank_top200.jsonl`。本步骤不修改 Fusion 权重；结果中同一 `query_id` 只应出现 v2 `job_id`。

### 4.6 必做 5：在真实输出路径接入三级岗位优先展示

现有适配器会将 Fusion 的 `job_id` 接回 v2 JD 元数据，调用既有 `role_aware_matching_service`，并输出“三级岗位优先、岗位内 JD 排序”的结构。示例：

```powershell
New-Item -ItemType Directory -Force "$runtime/production_role_aware" | Out-Null
& $python scripts/build_role_aware_fusion_results.py `
  --jobs $jobs `
  --fusion "$runtime/production_fusion/fusion_full.jsonl" `
  --role-data-dir backend-src/app/data/canonical_role_pool/v2 `
  --output "$runtime/production_role_aware/recommendations.jsonl" `
  --jd-top-k 10 `
  --role-top-k 1
```

在接前端前，算法组必须确认这条适配器所使用的岗位选择与线上已训练/已批准的岗位分类路径一致。适配器本身不训练或替代分类器，也不应把本地回退 Fusion 的表现当成线上效果。

### 4.7 必做 6：同集回归、人工抽检与最终切换

1. 以 v1/v2 使用同一份冻结金标集、同一评分口径、同一 Top-K 计算方式，输出并归档对照表。
2. 至少分别报告三级岗位 Top-1、可接受具体 JD Recall@2、Recall@3、严格 JD Top-1，以及分岗位方向的样本数和指标。不得只报总体值掩盖新增方向缺样本。
3. 新增产品、UI/UX、项目经理、安全合规等方向须补充来源独立的人工简历-JD 金标；旧 400 条技术金标不能覆盖它们。
4. 人工抽检同功能岗位内的不同技术栈、相邻岗位、标题相同职责不同、标题不同职责相同、跨域误入等边界样本。
5. 接口冒烟测试：以若干真实或脱敏简历从前端/API 跑完整链路，确认返回的 JD、三级岗位、技能证据和图谱展示使用同一 `canonical_role_id`。

只有第 1 至 5 项均通过、且 v2 不低于已冻结 v1 基线时，才设置：

```powershell
$env:JOB_HUNT_CANONICAL_ROLE_POOL_PATH = 'D:\job-hunt\artifacts\canonical_role_pool_v2\canonical_jobs.jsonl'
$env:JOB_HUNT_CANONICAL_ROLE_DATA_DIR = 'D:\job-hunt\backend-src\app\data\canonical_role_pool\v2'
```

这些变量需写入算法组实际使用的服务启动环境（例如 Docker Compose、CI/CD 或进程管理器），不是只在个人 PowerShell 会话临时设置。修改后重启对应服务，并在启动日志中记录 `role_pool_version=v2` 和两个哈希。

## 5. 可选后续优化，不是本次切换前置条件

| 优化项 | 时机 | 原因 |
| --- | --- | --- |
| 补充新增非技术岗位的 JD 与独立金标 | 优先进行 | 产品、设计、项目管理、安全合规的样本覆盖尚不足以宣称全域准确率。 |
| 岗位成熟度/覆盖度字段 | 下一个岗位池版本 | 可标识高频、中频、低样本专业和前沿岗位，避免将少量 JD 误解为数据错误。 |
| 调整 Fusion 权重、增加特征或更换语义模型 | 完成 v2 输入回归后 | 这是算法实验，需单独建立基线、消融和金标对照，不能混入本次数据版本迁移。 |
| 优化角色分类器 | 发现新增方向明确退化后 | 先确认问题来自分类、检索、具体 JD 排序还是金标；不应先改模型。 |
| 全量离线候选预计算 | 确有延迟/吞吐需求时 | 不是准确率评测前置。在线可先按请求检索；若预计算需严格做版本标识和失效管理。 |
| 将 2,161 条审核记录持续处理 | 滚动进行 | 每次审核后以新小版本发布，严禁静默并入正式 mapped 集。 |

## 6. 回滚与故障处置

### 6.1 立即回滚

不删除任何数据，恢复 v1 运行时变量或移除 v2 变量，然后重启服务：

```powershell
Remove-Item Env:JOB_HUNT_CANONICAL_ROLE_POOL_PATH -ErrorAction SilentlyContinue
Remove-Item Env:JOB_HUNT_CANONICAL_ROLE_DATA_DIR -ErrorAction SilentlyContinue
```

当前代码在变量未设置时默认读取：

```text
backend-src/app/data/canonical_role_pool/v1
```

若服务启动环境中显式配置了 v1 路径，则恢复为该原配置即可。Elasticsearch 应切回旧 index alias/旧索引名；Neo4j 查询应切回 v1 database/标签；Fusion 和向量路径应切回旧产物目录。保留 v2 文件和日志用于定位问题，不能以删除 v2 作为回滚手段。

### 6.2 触发回滚或停止切换的条件

- 运行时读取的 JD 哈希与 `runtime_manifest.json` 不一致；
- v2 候选中混入 v1 `job_id`，或同一 Fusion 批次混用两个版本；
- 新旧同集回归出现无法解释的显著退化；
- 新增方向没有独立金标，却准备对外宣称全域覆盖/准确率；
- 角色分类、具体 JD 排序或图谱展示使用的 `canonical_role_id` 不一致；
- 需要修改核心评分公式才能使 v2 能运行。

出现这些情况时，先回到 v1 服务、冻结 v2 输入和产物，再定位是数据映射、索引、特征 schema、服务配置还是评测口径问题。

## 7. 建议的交接验收清单

- [ ] 已核对 v2 JD 与目录 SHA-256。
- [ ] 已建立独立 `canonical_jobs_v2` Elasticsearch 索引并完成文档数核验。
- [ ] 已用线上实际语义模型对 v2 重新编码，且保存运行元数据。
- [ ] 已导入隔离的 Job-CanonicalRole-Skill 图，包含 `INSTANCE_OF` 与 `REQUIRES_SKILL`。
- [ ] KG 特征、BM25、语义、Fusion 文件使用同一组 `query_id` / `job_id`。
- [ ] 已用未改权重的 Fusion 完成 v1/v2 同集回归。
- [ ] 已补新增非技术岗位的人工金标并单独报告。
- [ ] 真实 API/前端完整链路已抽检通过。
- [ ] v1 索引、图库、文件与启动配置均可随时恢复。
- [ ] 负责人确认后才设定 v2 为默认岗位池。

## 8. 相关文件索引

| 用途 | 文件 |
| --- | --- |
| 岗位池建设和匹配原则 | `docs/role-pool-and-matching-principles.md` |
| 本地重建说明 | `docs/canonical-role-pool-v2-local-rebuild.md` |
| v2 运行时清单 | `artifacts/canonical_role_pool_v2/runtime_manifest.json` |
| v2 本地重建记录 | `artifacts/role_pool_runtime/v2/local_rebuild/local_rebuild_report.json` |
| v2 金标回归记录 | `artifacts/canonical_matching_eval_v2_400/manifest.json` |
| v2 构建器 | `scripts/build_canonical_role_pool_v2.py` |
| 运行时目录构建器 | `scripts/prepare_role_pool_runtime.py` |
| 本地重建器 | `scripts/rebuild_role_pool_v2_local_artifacts.py` |
| 岗位优先结果适配器 | `scripts/build_role_aware_fusion_results.py` |
| 现有 BM25 候选脚本 | `backend-src/scripts/retrieve_bm25_candidates.py` |
| 现有语义重排脚本 | `backend-src/scripts/rerank_semantic_bge.py`、`backend-src/scripts/rerank_semantic_text2vec.py` |
| 现有 Fusion 脚本 | `backend-src/scripts/run_fusion_pipeline.py` |
| 现有基础图导入器 | `backend-src/scripts/import_canonical_graph.py` |

