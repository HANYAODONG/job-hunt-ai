# 新岗位发现与动态图谱前端展示工作留痕

## 目标

将赛题要求的“新岗位发现真实闭环”和“岗位/技能随时间演化”从后端能力接入前端岗位演化中心，保证页面能展示来源、月份、阈值、证据和人工审核边界。

## 已完成

### 批量新岗位发现

- 岗位演化中心新增“批量新岗位发现”页签。
- 可按月份刷新版本化岗位事件流。
- 页面展示输入 JD、去重后 JD、未稳定归类记录、候选聚类、支撑 JD 数、来源数和触发阈值。
- 候选卡片展示候选二级方向、岗位定义草稿、必备技能、核心职责和来源 JD 证据。
- 明确标记“观察中/待人工审核/待正式发布”等状态。
- 明确提示候选不会自动写入正式岗位池；正式岗位仍需人工复核并分配 `canonical_role_id`。

后端只读接口：

```text
GET /api/v1/jd-update/discovery/batch?domain=company&month=2026-07&threshold=10
```

该接口读取当前公司岗位版本的 `job_update_event_stream.csv` 和 SQLite 审核队列，不执行写入，不自动发布岗位。触发规则为去重后的同类 JD 数量 `> 10`，并保留来源证据。

### 时间演化对比

- 时序分析页新增起始月份和结束月份选择。
- 增加时间窗口、岗位画像新增技能、下降技能和画像变化指标。
- 增加“前后岗位画像对比”卡片。
- 复用现有月度趋势、技能生命周期、技能迁移和 `profile-compare` 接口。
- 无数据时显示空值，不使用演示值冒充真实分析结果。

## 当前真实数据快照

本地独立接口测试结果：

- 当前月份：`2026-07`
- 输入 JD：`1541`
- 去重后 JD：`1541`
- 未稳定归类审核候选：`0`
- 候选聚类：`0`
- 触发阈值：去重后同类 JD `> 10`

因此页面显示“当前月份没有待审核的新岗位候选”是数据事实，不代表功能缺失。新增月份数据或审核队列记录后，点击“刷新批次”即可重新读取。

## 验证记录

- 后端语法检查：通过。
- `tests/test_discovery_service.py`：`2 passed`。
- 前端相关测试：`3 suites / 10 tests passed`。
- React production build：成功。
- 独立 FastAPI TestClient 请求 `/api/v1/jd-update/discovery/batch`：HTTP `200`。

## 运行注意

当前 18088 端口上的 uvicorn 进程是旧进程，新接口需要重启后端才能从浏览器访问。手动重启命令：

```powershell
cd D:\job-hunt\backend-src
$env:DISABLE_EXTERNAL_SERVICES="true"
$env:DISABLE_ELASTICSEARCH="true"
py -3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 18088
```

前端入口仍为 `http://localhost:18080`，进入“岗位演化中心”即可看到两个新增视图。
