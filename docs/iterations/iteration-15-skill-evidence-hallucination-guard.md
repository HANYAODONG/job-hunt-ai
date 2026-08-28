# 第六轮交付 — 叶骑瑞：能力幻觉防控与技能证据链

> 对应 `docs/分工6-任务书验收收尾.md` §4。目标：让图谱里的每个技能节点和岗位-技能关系都有证据，不是模型凭空生成。

## 1. 交付清单

| 任务书要求 | 产出 | 状态 |
| --- | --- | --- |
| 给 JD 技能抽取增加证据来源 | `SkillEvidenceService.extract_with_report` | ✅ |
| 给简历技能抽取增加证据来源 | 同上 + `extract_skills_with_evidence.py` CLI | ✅ |
| 区分四类来源 | `explicit / synonym / dictionary / inferred` | ✅ |
| 对推断类技能降置信度 | 推断置信度上限 0.55，标注 `hallucination_risk` | ✅ |
| 岗位-技能关系说明"为什么有边" | `explain_edge()` + Neo4j `create_job_skill_relationship_with_evidence` | ✅ |
| 禁止"AI 项目"推断高阶能力 | `HIGH_LEVEL_SKILLS` 白名单拦截 | ✅ |
| 错误抽取被拦截案例 | 单测 + 本文 §6 | ✅ |
| JD/简历技能提取准确率测试 | 金标集评测 harness（可复现，见 §7） | ✅ |

新增/修改文件：

```text
backend-src/app/services/skill_evidence_service.py          # 新增：证据链抽取核心服务
backend-src/scripts/extract_skills_with_evidence.py         # 新增：产出 JD/简历抽取样例的 CLI
backend-src/app/services/knowledge_graph_service.py         # 新增：带证据链的岗位-技能边
backend-src/tests/test_skill_evidence_service.py            # 新增：单元测试 + 拦截案例 + 准确率 harness
docs/iterations/iteration-15-skill-evidence-hallucination-guard.md  # 本文
```

## 2. 技能证据链字段设计

每条抽取出的技能都携带以下字段：

```jsonc
{
  "skill": "PyTorch",            // 归一后的标准技能名
  "source_type": "explicit",     // 来源：explicit/synonym/dictionary/inferred
  "matched_text": "PyTorch",     // 原文命中的表面形式
  "confidence": 0.98,            // 置信度
  "hallucination_risk": false,   // 是否为推断类（幻觉风险）
  "category": "AI框架",          // 技能类别
  "parent": "人工智能",          // 上位技能
  "evidence": "原文显式出现：原文出现 'PyTorch'，归一为标准技能 'PyTorch'，置信度 0.98"
}
```

## 3. 来源分类与置信度

| 来源 | 含义 | 默认置信度 | 示例 |
| --- | --- | --- | --- |
| `explicit` 原文显式出现 | 标准技能名原样出现在原文 | 0.98 | 原文有 "Python" → Python |
| `synonym` 同义词映射 | 别名/同义词出现在原文 | 0.90 | 原文有 "Machine Learning" → 机器学习 |
| `dictionary` 词典归一 | match_pattern / 归一化命中 | 0.85 | 原文有 "DA"（match_pattern 命中）→ 数据分析 |
| `inferred` 模型推断 | 原文没有，靠语义推断 | ≤ 0.55 | 见 §5 拦截案例 |

**关键设计：推断类置信度被硬性封顶在 0.55，永远低于词典命中（0.85）。**

## 4. 能力幻觉防控规则

1. **默认不推断**：`allow_inference=False`，只保留有原文/词典证据的技能，杜绝"凭空生成"。
2. **四类来源分级置信度**：见 §3。
3. **高阶技能白名单禁止推断**（`HIGH_LEVEL_SKILLS`）：

   ```text
   大模型训练、RLHF、分布式训练、SFT、DPO、模型量化、
   Megatron、DeepSpeed、vLLM、SGLang、Transformer、
   多模态大模型、强化学习、分布式计算、GPU、CUDA、RDMA
   ```

   这些能力必须靠显式/同义/词典命中，语义推断一律拦截。
4. **推断类降权 + 打标**：置信度封顶 0.55 且 `hallucination_risk=true`，低于 `min_confidence`（默认 0.5）直接丢弃。
5. **边界感知匹配**：ASCII 技能要求两侧非字母数字（避免 "C" 误匹配 "CSS"），单字符别名跳过。
6. **同一技能保留最强证据**：同一技能命中多个来源时只保留置信度最高的一条。

## 5. 拦截案例（错误能力推断被拦截）

输入简历文本：**"做过 AI 项目"**（没有任何训练/对齐相关证据）。

开启推断（模拟一个"过度联想"的模型）后：

| 技能 | 推断相似度 | 处理结果 | 原因 |
| --- | --- | --- | --- |
| 机器学习 | 0.9 | ✅ 保留（`inferred`，置信度 0.55） | 非高阶，允许推断但降权 |
| 大模型训练 | 0.9 | ❌ 拦截 | 高阶技能，禁止推断 |
| RLHF | 0.9 | ❌ 拦截 | 高阶技能，禁止推断 |
| RAG | 0.9 | ✅ 保留（`inferred`，0.55） | 非高阶 |

拦截记录输出：

```jsonc
{
  "blocked": [
    {"skill": "大模型训练", "source_type": "inferred", "blocked_reason": "高阶技能禁止推断，需原文显式证据"},
    {"skill": "RLHF",       "source_type": "inferred", "blocked_reason": "高阶技能禁止推断，需原文显式证据"}
  ]
}
```

这就是任务书要求的"不能因为出现 'AI 项目' 就直接推断 '大模型训练' 'RLHF' 等高阶能力"。

## 6. JD / 简历技能抽取样例

运行：

```bash
# JD 样例
python backend-src/scripts/extract_skills_with_evidence.py \
    --text "负责大模型应用开发，要求 Python、FastAPI、RAG、Prompt Engineering，熟悉 Machine Learning"

# 简历样例
python backend-src/scripts/extract_skills_with_evidence.py \
    --text "熟悉 Python 与 SQL，做过 AI 项目，了解 Machine Learning"
```

JD 样例输出（节选）：

```jsonc
{
  "skills": [
    {"skill": "Python", "source_type": "explicit", "confidence": 0.98, "matched_text": "python"},
    {"skill": "FastAPI", "source_type": "explicit", "confidence": 0.98},
    {"skill": "RAG", "source_type": "explicit", "confidence": 0.98},
    {"skill": "Prompt Engineering", "source_type": "explicit", "confidence": 0.98},
    {"skill": "机器学习", "source_type": "synonym", "confidence": 0.90, "matched_text": "machine learning"}
  ],
  "blocked": [],
  "summary": {"explicit": 4, "synonym": 1, "dictionary": 0, "inferred": 0, "blocked_count": 0}
}
```

## 7. JD / 简历技能提取准确率测试结果（可复现）

在 4 条金标样本（共 12 个金标技能）上做宏平均评测：

| 样本 | 金标技能 | 抽取结果 | P | R |
| --- | --- | --- | --- | --- |
| 要求 Python、SQL、Spark，负责数据管道建设 | Python/SQL/Spark/数据管道 | 全部命中，无多余 | 1.0 | 1.0 |
| 熟悉 Machine Learning 与 PyTorch | 机器学习/PyTorch | 全部命中 | 1.0 | 1.0 |
| 前端开发，要求 React、CSS | 前端开发/React/CSS | 全部命中 | 1.0 | 1.0 |
| 掌握 Kubernetes 与 Docker，做微服务 | Kubernetes/Docker/微服务 | 全部命中 | 1.0 | 1.0 |

**宏平均：Precision = 1.0，Recall = 1.0，F1 = 1.0**（样本规模 4，金标技能 12）。

> 说明：这是确定性金标小样本，用于验证证据链抽取的正确性（可复现、防回归）。大规模 100 条 JD 的准确率评测属于 §3 甘可欣（JD 清洗）与 §5 纪雨涵（前端全流程测试）的横向联动，本模块的 harness 可直接复用为评测骨架。

复现命令（单测内已固化同样指标）：

```bash
docker compose exec backend pytest tests/test_skill_evidence_service.py -q
```

## 8. 图谱边证据

新增 Neo4j 方法 `create_job_skill_relationship_with_evidence`，在 `REQUIRES_SKILL` 边上写入：

```text
source_type / matched_text / confidence / evidence
```

因此图谱中每条"岗位-技能"边都能回答"为什么有这条边"，例如：

```text
evidence = "原文显式出现：原文出现 'PyTorch'，归一为标准技能 'PyTorch'，置信度 0.98"
```

## 9. 验收对照

| 分工6 §4 验收重点 | 完成情况 |
| --- | --- |
| 每个技能节点和岗位-技能关系都有证据 | ✅ 证据链字段 + 图谱边证据方法 |
| 四类来源区分 | ✅ explicit/synonym/dictionary/inferred |
| 推断类降置信度 | ✅ 封顶 0.55 + hallucination_risk 标记 |
| 高阶能力不误推断 | ✅ HIGH_LEVEL_SKILLS 白名单拦截 |
| 输出拦截案例 | ✅ §5 + 单测 |
| 提取准确率测试结果 | ✅ §7 金标集 P/R/F1=1.0（可复现） |
