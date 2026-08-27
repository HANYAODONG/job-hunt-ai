# 第十四轮迭代：工作流六 JD 质量治理验收

## 本轮目标

完成分工六中的 JD 噪音、时滞、重复/疑似抄袭、要求膨胀和多源交叉验证，并形成可重复运行、可追溯和可量化的验收闭环。

## 新增内容

### 1. 全量 JD 质量审计

新增 `backend-src/scripts/audit_jd_quality.py`，从标准 `jobs.jsonl` 生成五个规定质量字段：

- `is_duplicate`
- `noise_score`
- `inflation_score`
- `source_count`
- `verified_by_multi_source`

同时保留 `description_raw`、`description_cleaned`、判定原因、重复来源和时滞证据。

### 2. 要求膨胀识别校准

在技能数量、强要求词、学历、年限和岗位族基线之外，增加普通岗位高年限、宽技能范围和模糊岗位高负担等岗位层级失配因素。该维度仍是当前最弱项，验收报告中保留真实误差，不通过调整统计口径隐藏问题。

### 3. 逐条多源证据链

新增以下字段：

- `record_source_count`
- `verified_by_multi_source_record`
- `verification_scope`
- `source_evidence`

`verification_scope` 明确区分：

- `record_duplicate_group`：同正文重复组的直接跨来源证据。
- `standard_job_family`：标准岗位族层面的跨来源支持。
- `single_source`：单一来源。

这样可以避免把岗位族统计误写成同一 JD 的直接跨站点印证。

### 4. DeepSeek 独立盲审

新增 `backend-src/scripts/review_jd_quality_with_deepseek.py`：

- DeepSeek 看不到现有规则预测。
- 每条样本独立判断两次。
- 引用证据必须能逐字回查到 JD 原文。
- 双票一致、平均置信度不低于 0.82 且证据有效时，形成伪人工金标。
- 其余样本进入冲突队列。
- 支持断点续跑和样本变化后的增量复核。

DeepSeek 结果在论文和答辩中应称为“LLM 辅助双投票伪人工金标”，不能称为正式人工金标。

### 5. 一键验收

运行：

```powershell
python scripts/run_workflow6_acceptance.py
```

该命令依次执行：

1. Docker 后端启动检查。
2. 16,574 条标准 JD 全量审计。
3. DeepSeek 200 条分层样本断点复核。
4. 五类案例和量化指标检查。
5. 最终 JSON 与 Markdown 验收报告生成。

## 当前验收结果

- 全量 JD：16,574 条。
- 五个规定字段完整率：100%。
- 来源证据完整率：100%。
- 重复案例：30 条。
- 噪音案例：20 条。
- 要求膨胀案例：20 条。
- 时滞案例：20 条。
- 多源验证案例：30 条。
- DeepSeek 复核：200 条，其中162条高置信一致、38条冲突、API错误0条。
- 五项 Macro-F1：90.96%。
- 重复 F1：100%。
- 噪音 F1：95.58%。
- 时滞 F1：100%。
- 多源验证 F1：97.87%。
- 要求膨胀 F1：61.33%，仍需后续优化。

当前五项验收标准按“Macro-F1不低于80%，重复、噪音、时滞分别不低于90%”通过。如果验收方要求每个维度分别达到80%，则要求膨胀维度尚未通过，必须如实说明。

## 测试

- JD 清洗、日期解析、岗位要求膨胀和来源证据链测试：7项通过。
- DeepSeek JD 盲审与防规则泄漏测试：2项通过。
- 既有 DeepSeek 金标流水线测试：7项通过。
