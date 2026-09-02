# 400 条人岗匹配测试说明

## 1. 测试目标

本测试验证系统在统一 canonical 岗位集合内，能否先确定简历所属的三级岗位，再从该三级岗位对应的真实 JD 中给出可接受的具体岗位候选。

最终成功单位是“简历”，不是 JD 条数：400 份简历各计算一次是否命中人工认可结果。

## 2. 测试数据

- 测试简历：400 份，全部唯一。
- 每份简历配套 5 条真实 canonical JD，共 2,000 条选项。
- 完整匹配池：10,964 条已映射 canonical JD，覆盖 65 个三级岗位。
- 每份简历的人工参考包括：标准 canonical 三级岗位，以及一个或多个可接受的具体 JD。

本版标注由专家 GPT 按统一规则完成，状态是首轮机器辅助标注草案；在真人岗位专家复核并冻结前，不能称为最终人工金标。

## 3. 评测流程

对每份简历执行以下流程：

1. 从简历提取规范化技能集合。
2. 使用训练集简历学习岗位区分权重。测试时不使用该案例的人工标签参与排序。
3. 在 canonical 三级岗位集合中计算岗位得分，选出最高分三级岗位。
4. 只在选中的三级岗位内部，对完整岗位池中的 JD 按技能覆盖、候选人技能精确度、F1 和偏好技能进行排序。
5. 取 JD 排名 Top-1、Top-2、Top-3、Top-5、Top-10，分别检查是否至少有一个 JD 属于人工认可集合。

评测只调用本地岗位池、简历和确定性评分逻辑，不启动 Docker，也不修改 BM25、语义模型、知识图谱或 Fusion 核心算法。Docker 在线服务未参与本次离线计算，因此本报告不是完整前端端到端运行证明。

## 4. 指标定义

### 三级岗位指标

- `role_top1_accuracy`：系统第一个三级岗位是否等于人工标准三级岗位。
- `role_top3_recall` / `role_top5_recall`：人工标准三级岗位是否出现在前 3/5 个三级岗位中。

### 具体 JD 指标

设一份简历人工认可的 JD 集合为 `G`，系统前 `K` 个 JD 为 `R@K`。若 `G ∩ R@K` 非空，则该简历在 JD Recall@K 上命中。

- `accepted_jd_recall_at_1`：第一个 JD 必须命中人工认可集合，最严格。
- `accepted_jd_recall_at_2`：前两个 JD 中至少一个命中。
- `accepted_jd_recall_at_3`：前 3 个 JD 中至少一个命中。
- `accepted_jd_recall_at_5` / `accepted_jd_recall_at_10`：前 5/10 个 JD 的候选覆盖能力。

采用 Recall@K 是因为同一现实岗位可能对应多个公司、城市、职级和职责相近的 JD。只要求唯一 Top-1 会把“同岗位的合理候选”误判为错误；但 Top-1 仍保留作为严格排序指标。

## 5. 本次结果

| 指标 | 结果 |
|---|---:|
| 三级岗位 Top-1 | 399/400 = 99.75% |
| 三级岗位 Top-3 | 399/400 = 99.75% |
| 三级岗位 Top-5 | 400/400 = 100% |
| 具体 JD Top-1 | 345/400 = 86.25% |
| 具体 JD Top-2 | 366/400 = 91.50% |
| 具体 JD Top-3 | 383/400 = 95.75% |
| 具体 JD Top-5 | 393/400 = 98.25% |
| 具体 JD Top-10 | 397/400 = 99.25% |

因此，若产品定义为“前两个候选 JD 中命中任一人工认可 JD 即算成功”，本次命中率为 91.50%；若定义为“前 3 个候选中命中即成功”，则为 95.75%。两者都不能表述成严格 Top-1 准确率。

## 6. 如何复现

```powershell
python scripts/annotate_canonical_matching_expert_gpt.py `
  --pack-dir artifacts/canonical_matching_review_v1

python scripts/evaluate_canonical_matching_two_stage.py `
  --pack-dir artifacts/canonical_matching_review_v1 `
  --output-dir artifacts/canonical_matching_eval_v1_400
```

主要输入：

- `artifacts/canonical_matching_review_v1/expert_gpt_cases.csv`
- `artifacts/canonical_matching_review_v1/expert_gpt_annotations.csv`
- `artifacts/canonical_role_pool_v1/data_group_current/canonical_jobs.jsonl`

主要输出：

- `manifest.json`：指标、输入哈希和评测协议。
- `case_metrics.csv`：400 份简历逐案例结果。
- `job_rankings_topk.csv`：每份简历的 JD Top-10 排名。
- `role_rankings.csv`：三级岗位排序结果。

## 7. 使用限制

1. 当前简历来自现有生成数据集，不是脱敏真实简历。
2. 当前标注是专家 GPT 首轮草案，不是双人盲标后的正式金标。
3. 因此结果适合比较算法版本、发现岗位边界和排序问题；在真人复核、真实简历替换和完整前端链路复测前，不应宣称为现实泛化准确率。
