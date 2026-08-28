# JD 质量治理规则

## 目标

该流程对企业岗位、政府岗位和历史标签岗位统一执行质量审计，解决分工六要求的 JD 噪音、时滞、重复/疑似抄袭、要求膨胀和多源交叉验证问题。所有清洗均保留原始描述和判定依据，避免不可追溯的数据覆盖。

## 输出字段

- `is_duplicate`：标准化正文完全相同或近似度达到阈值。
- `duplicate_type`：`exact` 或 `near_duplicate`。
- `noise_score`：模板占位、企业文化、团队宣传、福利、联系方式、重复段落和低信息量的综合分数。政府招录中的咨询电话属于必要招考证据，不按企业 JD 噪音处理。
- `inflation_score`：技能数量、强要求用语、工作年限和同岗位族偏离程度的综合分数。
- `staleness_score` / `is_stale`：相对数据集中最新有效发布日期的时滞。
- `source_count`：同一标准岗位族可追溯的来源-年份证据数量。
- `verified_by_multi_source`：至少跨来源类型，或同时跨来源名称和年份得到支持。
- `record_source_count` / `verified_by_multi_source_record`：同正文重复组中可直接回查的跨来源记录数量和验证结论。
- `verification_scope`：区分 `record_duplicate_group`、`standard_job_family` 和 `single_source`，防止把岗位族支持误写成同一 JD 的直接印证。
- `source_evidence`：保存当前记录来源、同正文来源匹配、岗位族来源样本、年份、URL或原始文件。
- `quality_flags`：供下游过滤的统一质量标签。

## 阈值

- 噪音：`noise_score >= 0.35`。明确占位符、模板错误、团队/公司宣传和企业文化按类别赋权；长段落只标记而不整段删除，避免误删岗位职责。
- 岗位要求膨胀：`inflation_score >= 0.65`。
- 时滞：发布日期缺失或距参照日期超过 365 天。
- 近重复：SimHash 候选的正文相似度不低于 0.86。

## 使用原则

历史 JD 不会被直接删除。系统用 `is_stale` 标记其不适合代表当前招聘需求，但仍保留给岗位能力演化分析。重复 JD 保留首条证据，后续记录通过 `duplicate_of` 指向首条记录。清洗后的 `description` 可进入检索和技能抽取，`description_raw` 用于审计复核。

## 运行

```powershell
python scripts/run_workflow6_acceptance.py
```

该命令在 Docker 后端中依次执行全量审计、DeepSeek 断点复核和最终报告构建。产物位于 `artifacts/jd_quality_audit/`、`artifacts/jd_quality_deepseek_review/` 和 `artifacts/workflow6_acceptance/`。DeepSeek 独立盲审与最小人工核验方式见 `docs/jd-quality-deepseek-review.md`。
