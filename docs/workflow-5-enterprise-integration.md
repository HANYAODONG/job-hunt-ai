# 工作流 5 企业端数据接入

## 完成范围

本轮把标准岗位和标准候选画像接入企业端，不修改工作流 1 的字段生成逻辑，也不替代工作流 2-4 的语义、图谱和融合模型。

- `/recruitment`：读取企业岗位，展示详情、技能、来源、发布时间并保存人工修改。
- `/candidates`：针对选中岗位扫描标准候选池，输出匹配分、技能命中、技能差距、理由和人工筛选状态。
- `/signals`：在 Elasticsearch 不可用时仍可读取标准岗位总量；新岗位候选内容目前仍是 Mock 审核样例。
- BM25：支持 sample 和 full 两种索引重建方式，Elasticsearch `_id` 始终使用标准 `job_id`。

## 后端接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/v1/talent/recruitment/jobs` | 企业岗位列表，支持查询、状态、来源和分页 |
| GET | `/api/v1/talent/recruitment/jobs/{job_id}` | 岗位详情 |
| PUT | `/api/v1/talent/recruitment/jobs/{job_id}` | 保存 JD 人工覆盖字段或创建企业 JD |
| GET | `/api/v1/talent/recruitment/jobs/{job_id}/candidates` | 候选人可解释排序结果 |
| PATCH | `/api/v1/talent/recruitment/jobs/{job_id}/candidates/{candidate_id}/stage` | 保存人工筛选状态 |
| GET | `/api/v1/talent/market/stats` | 标准岗位来源、岗位族、技能和年份统计 |

岗位人工修改和候选人状态保存在 `artifacts/runtime/talent_state.json`，不会改写工作流 1 的标准 JSONL。

## 候选排序 baseline

当前企业端 baseline 的分数由三部分组成：技能覆盖 65%、岗位族/标准类别 25%、经验要求 10%。返回结果同时包含各维度分数、命中技能、缺失技能和文本理由。它用于打通企业端数据出口和人工审核流程，不能替代工作流 4 的 BM25、BGE-M3、Neo4j 与 Fusion 最终排序。

## Elasticsearch 重建

先启动 Elasticsearch：

```powershell
docker compose up -d elasticsearch
```

小样本冒烟测试：

```powershell
python .\backend-src\scripts\index_chinese_jobs.py --mode sample --sample-size 1000 --recreate
```

全量重建：

```powershell
python .\backend-src\scripts\index_chinese_jobs.py --mode full --recreate
```

默认输入为 `artifacts/dataset_iteration_05/jobs.jsonl`。`sample` 只限制写入条数，不会重编号，因此 sample/full 的同一岗位拥有相同 `_id`。

## 真实与 Mock 边界

| 页面/能力 | 当前状态 |
| --- | --- |
| 招聘岗位列表、详情、编辑状态 | 真实标准数据接口，后端不可用时显示 Mock 回退标识 |
| 候选池匹配、技能差距、筛选状态 | 真实标准数据接口，可解释 baseline |
| 市场岗位总数 | 真实标准数据统计 |
| 新岗位发现审核样例 | Mock，离线发现结果尚未接成查询接口 |
| 文件上传后自动解析进候选池 | 页面级演示，尚未持久化到标准候选数据 |

## 验证

```powershell
D:\python\python.exe -m unittest backend-src.tests.test_talent_data_service
npm.cmd run build --prefix frontend-src
```

BM25 单元测试需要当前 Python 环境安装 `elasticsearch` 依赖；完整索引验证还需要 Docker Desktop 中的 Elasticsearch 正常运行。
