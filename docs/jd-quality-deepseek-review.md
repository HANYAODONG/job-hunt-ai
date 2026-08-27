# JD 质量 DeepSeek 复核

## 定位

该流程用 DeepSeek API 代替大部分人工初审，生成“伪人工金标”，用于验证重复、噪音、要求膨胀、时滞和多源验证规则。它不是论文意义上的正式人工金标，最终报告中应如实称为“LLM 辅助双投票标注”或“伪人工金标”。

## 自动复核流程

1. 从全量 JD 中读取 200 条分层验收样本。
2. 每条 JD 由 DeepSeek 独立盲审两次，模型看不到现有规则预测。
3. 引用证据必须能逐字回查到 JD 原文，否则判为无效。
4. 两票五项标签全部一致、平均置信度不低于 0.82、证据有效且模型未请求人工复核时，进入 `pseudo_human_gold.jsonl`。
5. 其余样本进入 `conflict_review_queue.jsonl`，不作为自动验收真值。
6. 只在高置信一致集上计算规则的 Precision、Recall、F1 和 Accuracy。

## 运行

```powershell
python scripts/review_jd_quality_with_deepseek.py --overwrite
```

需要在 `.env` 中配置 `DEEPSEEK_API_KEY`。脚本支持断点续跑，不会把 API Key 写入产物。

## 产物

- `deepseek_jd_quality_judgments.jsonl`：全部成功判断及两轮证据。
- `pseudo_human_gold.jsonl`：高置信一致的伪人工金标。
- `conflict_review_queue.jsonl`：两票冲突、低置信或证据不足的样本。
- `deepseek_errors.jsonl`：API 或格式错误。
- `evaluation_report.json`：覆盖率、五项指标、配置、输入哈希和 token 用量。

## 最小人工核验

比赛提交前仍建议由队员完成很小的一轮人工确认：

1. 优先检查 `conflict_review_queue.jsonl` 中所有样本。
2. 从 `pseudo_human_gold.jsonl` 随机抽查 20 至 30 条。
3. 对每条只填写五个布尔标签，并在错误项记录一句原文证据。
4. 若抽查一致率低于 90%，扩大样本并调整规则；达到 90% 后记录检查人、日期和一致率。

人工判断口径：重复看正文语义是否实质相同；噪音看是否存在与岗位能力无关的大段模板；要求膨胀看岗位层级与技能、年限是否明显失衡；时滞按参照日期超过 365 天或日期缺失判断；多源验证只看来源类型、来源名称和年份证据，不凭主观判断。
