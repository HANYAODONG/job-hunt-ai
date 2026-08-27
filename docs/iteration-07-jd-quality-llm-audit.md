# 第七次迭代：JD 通胀检测与大模型证据约束

## 迭代原因

任务书中要求解决多源异构岗位数据的“时滞”和“噪音”问题，并进行能力“幻觉”防控。当前系统已经具备岗位动态更新、技能抽取、图谱展示和人岗匹配链路，但在 JD 入库或入图前还缺少一个显式的数据质量筛选层。

本轮新增 JD 通胀与噪声检测模块，用于在岗位技能进入能力图谱前识别以下风险：

- 岗位要求通胀：同一岗位堆叠过多技能、跨多个技术域、岗位级别与经验要求不一致。
- 模板噪声：大量通用软性要求或招聘模板语句，不适合直接作为能力节点依据。
- 证据不足：JD 文本过短、技能证据稀疏，不适合直接以高权重进入图谱。

这里的“能力幻觉防控”不指普通规则检测本身，而是指大模型参与 JD 复核、技能解释或总结生成时，必须被 JD 原文和规则结果约束，不能凭空添加能力结论。

## 本轮目标

- 后端提供可调用的 JD 通胀与噪声检测接口。
- 默认规则模式即可运行，不依赖大模型 API。
- 配置 DeepSeek API 后，可由大模型生成更适合前端展示和答辩说明的总结。
- 前端新增一个可视化页面展示审核结果、风险等级、入图策略和大模型总结。

## 已实现内容

### 后端

新增 `app/services/jd_quality_service.py`：

- 支持从 `artifacts/dataset_iteration_05/sample_pack/jobs_sample.jsonl` 或 `jobs.jsonl` 读取样例 JD。
- 对每条 JD 计算 `inflation_score`、`noise_score`、`evidence_risk`。
- 输出 `risk_level`、`issues`、`evidence`、`suspected_inflated_skills`。
- 给出图谱处理策略：
  - `hold_for_review`：高风险，暂缓入图，进入人工复核。
  - `downweight_and_trace`：中风险，降权入图并保留证据。
  - `allow_with_trace`：低风险，允许入图并保留来源。
- 支持 DeepSeek 增强审核和批次总结，但 API key 只通过环境变量读取，不写入仓库。

新增 `app/api/endpoints/jd_quality.py`：

- `POST /api/v1/jd-quality/audit`：审核单条 JD。
- `POST /api/v1/jd-quality/batch`：审核前端或脚本传入的一批 JD。
- `GET /api/v1/jd-quality/sample`：读取本地样例数据并审核。
- `GET /api/v1/jd-quality/summary`：输出批次质量摘要。

### 前端

新增 `src/pages/JdQualityPage.js` 与 `src/pages/JdQualityPage.css`：

- 页面入口：`/jd-quality`。
- 企业侧导航新增 `JD 质检`。
- 页面包含动态浅蓝色边框的总结卡片，用于展示规则审核或 DeepSeek 总结。
- 展示本批次 JD 总数、高风险数量、中风险数量、平均通胀风险。
- 支持按风险等级筛选 JD。
- 每条 JD 展示风险分、证据、疑似通胀技能和图谱入库建议。

## 大模型介入方式

当前采用“规则先行，大模型增强”的轻量方案：

1. 规则层先对 JD 做确定性审查，保证没有 API key 时系统仍可运行。
2. 大模型只读取规则层结果和 JD 原文摘要，不直接凭空生成技能。
3. 大模型输出审核总结、风险解释和处理建议，主要用于展示和人工复核辅助。
4. 高风险 JD 不直接更新图谱；DeepSeek 复核必须基于输入证据，降低大模型在解释或总结中产生能力幻觉的概率。

## 使用方式

启动后访问：

```text
http://localhost:18080/jd-quality
```

如需启用 DeepSeek 增强总结，在启动后端前设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY="你的 DeepSeek API Key"
```

不要把 API Key 写入 `.env` 后上传，也不要提交到 GitHub。

## 后续工作

- 将 JD 通胀与噪声检测接入真实 JD 导入流程，在写入 `job_update` 正式库前自动执行。
- 把审核结果保存为可追溯记录，支持后续作品文档中的量化分析。
- 设计至少 100 条 JD 测试用例，统计 JD 解析准确率、简历提取准确率和匹配准确率。
- 前端可进一步展示“被拦截 JD 示例”和“入图前后图谱变化对比”。
