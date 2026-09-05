# 新岗位发现与动态图谱演化测试方案

## 1. 测试目的

验证前端能够展示赛题要求的两条能力闭环：

1. 新月份 JD 进入系统后，经过归类、去重、候选聚类、阈值判断和人工审核，形成可追溯的新三级岗位候选。
2. 岗位画像和技能关系能够按月份对比，展示新增、下降、稳定技能以及岗位画像变化。

本测试不修改人岗匹配核心算法，也不自动发布新岗位。

## 2. 环境

- 前端：`http://localhost:18080`
- 后端：`http://localhost:18088`
- 后端启动时建议关闭不可用的外部服务：

```powershell
cd D:\job-hunt\backend-src
$env:DISABLE_EXTERNAL_SERVICES="true"
$env:DISABLE_ELASTICSEARCH="true"
py -3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 18088
```

## 3. 测试入口

进入前端“岗位演化中心”：

- `批量新岗位发现`：月度批次、候选聚类、来源 JD 和审核边界。
- `时序分析`：岗位技能趋势、月份窗口和前后画像对比。
- `实时岗位演化`：单条 JD 的归类、技能变化和证据链。
- `人工优化`：岗位定义修改和发布前检查。

## 4. 真实数据验收

### 4.1 批量发现接口

```text
GET /api/v1/jd-update/discovery/batch?domain=company
```

检查以下字段存在且与页面一致：

| 字段 | 含义 |
| --- | --- |
| `month` | 默认最新数据月份 |
| `input_jd_count` | 该月份输入事件数 |
| `deduplicated_jd_count` | 按原始岗位 ID 去重后的数量 |
| `unmapped_jd_count` | 当前审核队列中未稳定归类记录数 |
| `cluster_count` | 候选聚类数量 |
| `trigger_threshold` | 新岗位数量阈值，默认 10 |
| `candidates` | 候选聚类及来源证据 |
| `guardrails` | 不自动发布、人工审核和 canonical_role_id 约束 |

当前本地验收基线：`2026-07`、输入 `1541`、去重后 `1541`、候选聚类 `0`。页面应显示空状态，并说明新增 JD 会先进入归类和审核队列；这属于真实数据结果。

### 4.2 动态演化接口

使用现有真实接口检查月份和画像变化：

```text
GET /api/v1/jd-update/analytics/months?domain=company
GET /api/v1/jd-update/analytics/job-trend?domain=company&standard_job=<岗位>&month_start=<起始月份>&month_end=<结束月份>
GET /api/v1/jd-update/analytics/profile-compare?domain=company&standard_job=<岗位>&from_month=<起始月份>&to_month=<结束月份>
GET /api/v1/jd-update/analytics/lifecycle?domain=company&standard_job=<岗位>
GET /api/v1/jd-update/analytics/skill-migration?domain=company
```

页面验收点：

- 起始月份和结束月份来自接口，不手工写死；
- 时间窗口、增减技能和画像变化数随岗位/月份切换更新；
- 前后画像卡片展示两个时间点的技能集合；
- 没有数据时显示空值或空状态，不使用 mock 值冒充真实结果。

## 5. 隔离演示批次

真实当前批次没有触发新岗位阈值时，使用隔离测试数据证明触发逻辑，不把测试记录写入正式岗位池：

1. 准备一个临时月份，例如 `2099-01`，构造至少 12 条不同 `job_id` 的同类 JD；每条保留职责、要求、来源和月份。
2. 其中至少包含 2 个来源主体，避免同一来源重复抓取假满足阈值。
3. 运行批次分析，确认：
   - 去重后支撑 JD 数为 12；
   - `threshold_met=true`；
   - 状态为“待人工审核”；
   - 页面展示候选二级方向、核心职责、必备技能和来源 JD 证据；
   - 系统没有修改标准岗位词典、岗位池或图谱正式节点。
4. 在页面中人工编辑候选定义，提交岗位提案；检查状态变为“待正式发布”。
5. 只有明确点击正式发布后，才检查标准岗位词典、SQLite 岗位表和事件流是否新增记录，并确认产生 `canonical_role_id`。
6. 测试结束后删除临时测试数据或恢复测试数据库备份，不能把 `2099-01` 数据用于正式评测。

## 6. 完整演示脚本

建议录制或截图以下顺序：

1. 打开“批量新岗位发现”，显示月份和 5 项批次指标。
2. 展开候选卡片，展示“支撑 JD 数 / 来源数 / 候选二级方向”。
3. 展开“来源 JD 证据”，展示岗位名、月份和原始 ID。
4. 切换到“时序分析”，选择一个有多个月份数据的标准岗位。
5. 选择起始月和结束月，展示新增技能、下降技能和前后画像对比。
6. 返回“实时岗位演化”，提交一条 JD，展示归类、技能变化和人工确认状态。
7. 在“人工优化”展示发布前检查，说明候选不会绕过人工审核进入正式岗位池。

## 7. 通过标准

- 页面能访问真实批次接口，接口 HTTP `200`；
- 批次指标与接口 JSON 一致；
- 候选卡片包含可追溯来源证据；
- `>10` 规则只对去重后的同类 JD 生效；
- 候选未审核前不改变正式岗位池；
- 月份切换后趋势和画像对比确实变化；
- 截图、接口 JSON、启动日志和测试时间一并留存。

## 8. 当前已完成的本地验证

- 后端已重启，18088 使用最新代码；
- `/api/v1/jd-update/discovery/batch?domain=company` 返回 HTTP `200`；
- 当前真实批次返回 `2026-07 / 1541 / 1541 / 0 / 0`；
- 后端发现服务测试：`2 passed`；
- 前端岗位演化、发现和 API 测试：`10 passed`；
- 前端 production build：成功。
