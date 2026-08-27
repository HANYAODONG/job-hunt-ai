# 第五轮交付 — 叶骑瑞：语义模型、诊断结果与学习路径支撑

> 对应 `docs/分工5.md` §7。负责页面：`/diagnosis`、`/learning`。

## 1. 交付清单

| 任务 | 产出 | 状态 |
| --- | --- | --- |
| 语义向量与重排产物维护 | `backend-src/scripts/rerank_semantic_bge.py`、`rerank_semantic_text2vec.py`（已有，保持可用） | ✅ |
| `/diagnosis` 稳定字段 | 新增 `POST /api/v1/diagnosis/analyze` | ✅ |
| `/learning` 最小输出 | 新增 `POST /api/v1/learning/plan`、`POST /api/v1/learning/plan-from-diagnosis`，前端已接入 | ✅ |
| 轻量模型实验 | `evaluate_semantic_rerank.py` 扩展为四方案对比（含 BM25+BGE+技能覆盖） | ✅ |
| 单测 | `tests/test_diagnosis_service.py`、`tests/test_learning_plan_service.py` | ✅ |

新增/修改文件：

```text
backend-src/app/services/learning_plan_service.py      # 新增：学习路径纯函数生成
backend-src/app/services/diagnosis_service.py          # 新增：诊断稳定字段纯函数
backend-src/app/api/endpoints/learning.py              # 新增：学习路径接口
backend-src/app/api/endpoints/diagnosis.py             # 新增：诊断接口
backend-src/app/main.py                                # 注册两个新路由
backend-src/scripts/evaluate_semantic_rerank.py        # 扩展四方案对比 + 样本规模列
backend-src/tests/test_learning_plan_service.py        # 新增单测
backend-src/tests/test_diagnosis_service.py            # 新增单测
frontend-src/src/services/intelligenceApi.js           # 新增 generateLearningPlan / diagnosePersonRole
frontend-src/src/services/talentApi.js                 # getLearningPlan 接真实接口
docs/frontend-backend-gap-list.md                      # 更新 /diagnosis、/learning 状态
```

## 2. 语义向量与重排产物维护

离线/在线产物由两个脚本统一生成，输出路径与格式已固化：

```text
artifacts/semantic_bge/
    jobs_embeddings.npy            # BGE-M3 岗位向量缓存
    jobs_embedding_ids.json        # 岗位 ID 映射（embedding.ids）
    semantic_rerank_top200.jsonl   # 重排结果（semantic_score / semantic_rank）
    run_metadata.json              # 模型名、维度、编码耗时、峰值内存

artifacts/semantic_text2vec/
    jobs_embeddings.npy
    jobs_embedding_ids.json
    semantic_rerank_top200.jsonl
    run_metadata.json
```

运行命令（sample 优先，本地跑不动 full 时使用 `--max-jobs`）：

```bash
# text2vec 轻量模型
python backend-src/scripts/rerank_semantic_text2vec.py --max-jobs 200

# BGE-M3 对照组
python backend-src/scripts/rerank_semantic_bge.py --max-jobs 200

# 跳过离线编码、直接用已有向量缓存做重排
python backend-src/scripts/rerank_semantic_bge.py --skip-encode
```

在线接口 `POST /api/v1/semantic/rerank` 已存在：候选带文本时实时编码，
仅传 `job_id` 时读取预计算向量索引；语义模型不可用时回退到字符 n-gram 向量。

## 3. `/diagnosis` 稳定字段契约

新增 `POST /api/v1/diagnosis/analyze`，请求与返回如下：

```jsonc
// 请求
{
  "candidate_id": "resume_000001",
  "job_id": "job_xxx",
  "job_title": "大模型应用工程师",
  "candidate_skills": ["Python", "FastAPI"],
  "job_required_skills": ["Python", "RAG", "Agent 工作流"],
  "query_text": "简历摘要...",
  "job_text": "岗位描述...",
  "bm25_score": 0.82,
  "semantic_score": null,
  "job_family_match": 1.0
}

// 返回（分工5 §7.2 要求字段）
{
  "candidate_id": "...",
  "job_id": "...",
  "candidate_skills": [...],      // 候选人技能
  "target_job_skills": [...],     // 目标岗位技能
  "matched_skills": [...],        // 匹配技能
  "missing_skills": [...],        // 缺失技能
  "skill_coverage": 0.33,
  "semantic_score": 0.68,         // 语义相关度
  "final_score": 0.42,            // 综合推荐分
  "score_breakdown": {...},
  "explanation": "匹配技能 1 项，待补充技能 2 项，综合匹配度 42%。"
}
```

说明：

- 语义分 `semantic_score` 优先使用传入值；缺省时自动用 `NLPService` 计算
  （sentence-transformers → 字符 n-gram 回退 → 词级 Jaccard 回退）。
- `final_score` 复用 `fusion_scoring_service.fuse_single` 的分层融合公式，与
  前端全链路使用的融合口径一致，保证“综合推荐分”可对齐。
- 该接口是无基础设施依赖的纯函数实现，便于联调与单测；前端主链路仍走
  `uploadResume → BM25 → semantic → KG → fusion` 的完整流水线。

## 4. `/learning` 最小输出接口

新增两个接口：

```text
POST /api/v1/learning/plan
POST /api/v1/learning/plan-from-diagnosis
```

`/learning/plan` 返回（对应分工5 §7.3 的最小字段）：

```jsonc
{
  "target_role": "大模型应用工程师",
  "missing_skills": [
    {"skill": "Agent 工作流", "priority": "high", "reason": "..."}
  ],
  "stages": [
    {
      "id": "stage-1",
      "skill": "Agent 工作流",
      "priority": "high",
      "learning_stage": "阶段 1",
      "title": "Agent 工作流专项实践",
      "suggestion": "...",
      "resources": ["LangChain 官方文档", "..."]
    }
  ],
  "resources": [...],
  "profile": "陈同学",
  "target_version": "v1.2",
  "match_score": 0.72,
  "progress": 33,
  "current_stage": "阶段 1",
  "gap_count": 3,
  "updated_at": "2026-08-25 10:00"
}
```

前端链路：

```text
/diagnosis 生成学习路径按钮
  -> localStorage.careerTarget = { role, version, score, gaps }
  -> 跳转 /learning
  -> getLearningPlan() 读取 careerTarget
  -> POST /api/v1/learning/plan
  -> 归一化为页面 stages；后端不可用时回退 mock
```

优先级排序：`high → medium → low`；阶段状态自动分配（首个“进行中”，其余“未开始”）。
资源建议由内置技能建议库确定性生成（Agent/RAG/评测/可观测/Prompt/向量等），
不依赖 LLM，后续可替换为 LLM 解释。

## 5. 模型实验方案（四方案对比）

实验目标：在相同 BM25 Top200 候选集与金标对上，对比四套排序方案的 Recall@K / MRR / NDCG。

```text
A. BM25                         （baseline）
B. BM25 + text2vec              （轻量中文语义）
C. BM25 + BGE-M3                （多语言语义）
D. BM25 + BGE-M3 + 技能覆盖     （融合 final_score）
```

评测脚本：

```bash
# 单模型评测
python backend-src/scripts/evaluate_semantic_rerank.py \
    --ranking artifacts/semantic_bge/semantic_rerank_top200.jsonl \
    --labels artifacts/dataset_iteration_05/label_pairs_gold.jsonl \
    --score-field semantic_score --rank-field semantic_rank

# 四方案对比（D 方案读取 artifacts/fusion_ranking/fusion_full.jsonl）
python backend-src/scripts/evaluate_semantic_rerank.py --compare-all \
    --labels artifacts/dataset_iteration_05/label_pairs_gold.jsonl \
    --fusion artifacts/fusion_ranking/fusion_full.jsonl
```

输出报告 `artifacts/semantic_text2vec/eval_report.json` 包含：

```text
Recall@K / NDCG@K / MRR（K 默认 5,10,20,100）
样本规模（evaluated_queries、total_labeled_pairs）
运行耗时（encode_time_sec、avg_query_encode_ms、peak_memory_mb）
```

复现前提：`artifacts/dataset_iteration_05/`（jobs.jsonl、candidate_profiles.jsonl、
label_pairs_gold.jsonl、sample_pack）与 BM25/语义/融合产物需先生成；文件缺失时
评测脚本会以“文件缺失”标记该方案而不中断。本地跑不动 full 时，用
`--max-jobs` 生成 sample 级向量缓存再评测。

## 6. 验收标准对照

| 分工5 §7 验收标准 | 完成情况 |
| --- | --- |
| sample 数据能跑通语义重排 | `rerank_semantic_*.py --max-jobs` 支持 sample 级编码+重排；在线 `/semantic/rerank` 可实时编码 |
| `/diagnosis` 能用到语义分数或语义排序结果 | 前端全链路已使用 `semantic_score` 参与融合；新增 `/diagnosis/analyze` 直接返回 `semantic_score` |
| `/learning` 至少有一版接口方案或 JSON 产物 | `POST /api/v1/learning/plan` + `plan-from-diagnosis`，前端已接入（mock 兜底） |
| 模型实验结果可复现 | `evaluate_semantic_rerank.py --compare-all` 输出四方案 Recall@K/MRR/NDCG/耗时/样本规模 |

## 7. 已知缺口 / 后续负责人

- 语义向量缓存（`.npy`）与重排产物属于本地生成产物，**不提交仓库**；数据目录
  由李佳蔓（数据放置）与甘可欣（BM25 索引）配合补齐后，脚本即可在 sample 上复现。
- `semantic_score` 与 KG 的 `job_id` 对齐仍依赖魏昊朗（KG）与甘可欣（BM25 索引）
  统一 ID 契约；sample 链路内部已自洽。
- 学习路径的 `resources` 目前是确定性模板，如需个性化解释可后续接 LLM（分工5 未强制）。
