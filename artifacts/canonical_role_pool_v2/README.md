# canonical_role_pool_v2

这是基于 `canonical_role_pool_v1/data_group_current` 和
`incremental_nontechnical_20260901_v2` 生成的岗位池发布候选，不覆盖 v1。

## 文件

- `canonical_jobs.jsonl`：仅包含 `role_mapping_status=mapped` 的 11,361 条 JD，可作为后续索引构建输入。
- `canonical_roles.csv`：78 个岗位身份，其中 76 个 `active`，其余为 `review_only`。
- `role_mapping_review.jsonl`：v1 历史审核队列与 v2 新候选审核队列，未丢弃原始字段。
- `deduplication_report.json`：新增快照的标题+正文去重记录。
- `role_pool_report.json`：版本统计、质量门禁和输出路径。

## 当前决策

已激活的新增角色：产品经理、数据产品经理、技术产品经理、安全合规工程师、研发项目经理、游戏项目经理、交付项目经理、IT项目经理、UI/UX设计师。

这些岗位当前本地覆盖度不均衡（去重后 1-11 条），因此保留覆盖度和来源证据字段；岗位身份本身已按用户决策进入 active。剩余未形成可靠边界的候选仍在审核队列。

## 使用边界

本目录是当前默认运行版本。运行时使用 `canonical_jobs.jsonl` 作为轻量匹配和图谱的共同输入；完整链路启用时，BM25、向量、Fusion 和图谱导入也应使用同一文件，并把岗位目录切换到配套的 `canonical_roles.csv`。v1 文件保持不变，可随时回滚。
