# 工作流 5：BM25 召回与候选集服务

## 1. 目标与边界

本工作流负责把统一岗位数据写入 Elasticsearch，并根据简历或查询文本快速召回 Top100/Top200 岗位，为后续语义重排、知识图谱和融合排序提供稳定候选集。

负责内容：

- 岗位数据到 Elasticsearch 文档的转换和批量导入。
- 索引 mapping、中文分析器和 BM25 字段权重。
- 单条查询和批量简历召回。
- 输出 BM25 分数、排名和候选岗位 ID。
- 使用工作流 1 提供的金标计算 Recall@K、MRR、NDCG 等 baseline 指标。

不负责内容：

- BGE/Embedding 重排。
- 技能抽取、技能标准化和 Neo4j 图谱构建。
- 最终融合分数和前端推荐解释。
- 继续开发早期岗位爬虫。

## 2. 当前数据

| 数据 | 路径 | 数量 | 用途 |
| --- | --- | ---: | --- |
| 大公司岗位 | `dataset/incoming/job_bigcompany_final.csv` | 12,675 | 企业岗位 BM25 主数据 |
| 标准岗位词典 | `dataset/incoming/standard_job_title_dictionary.csv` | 71 | 岗位名称和岗位类别归一参考 |
| 合成简历 | `dataset/incoming/synthetic_detailed_resumes.csv` | 5,500 | 批量召回和压力测试 |
| 公务员岗位 | `dataset/cleaned/government_jobs_2026_normalized.jsonl` | 20,714 | 独立公务员检索数据 |

大公司岗位共有 69 个非空 `standard_job` 值，`job_id` 当前无重复。企业岗位缺少公司和地点字段，这两个字段不能作为本轮主要排序信号。

## 3. 数据流

```text
incoming CSV / government JSONL
        |
        v
岗位适配与字段校验
        |
        v
Elasticsearch 岗位索引
        |
        v
简历 -> query_text_bm25 -> BM25 TopK
        |
        v
候选集 JSONL / FastAPI 响应
        |
        +--> 工作流 2：语义重排
        +--> 工作流 3：图谱与技能证据
        +--> 工作流 4：融合排序与前端
```

## 4. 统一岗位契约

工作流 5 内部建议使用下面的最小岗位结构，避免检索层直接依赖某一份 CSV 的列名：

```json
{
  "job_id": "JOB00001",
  "title": "后端开发工程师岗",
  "job_family": "后端开发工程师",
  "description": "岗位职责与岗位要求合并后的文本",
  "skills": ["Python", "MySQL", "Redis"],
  "domain_context": "跨境电商",
  "company": "",
  "location": "",
  "source": "bigcompany_processed",
  "publish_time": "2026/7/13"
}
```

新企业岗位字段映射：

| 新 CSV 字段 | 统一字段/用途 | 处理方式 |
| --- | --- | --- |
| `job_id` | `job_id` | 原样保留，作为 Elasticsearch `_id` |
| `job_title` | `title` | 原始岗位标题，高权重检索字段 |
| `standard_job` | `job_family` | 标准岗位名称，高权重检索和过滤字段 |
| `job_responsibility` | `description` | 与岗位要求、详细描述合并 |
| `job_requirement` | `description` | 与岗位职责、详细描述合并 |
| `skills` | `skills` | 解析为技能列表 |
| `traditional_skills` | `skills` | 与技能列表合并并去重 |
| `new_skills` | `skills` | 与技能列表合并并去重 |
| `domain_context` | `domain_context` | 独立索引，并进入汇总文本 |
| `detailed` | `description` | 作为补充文本，避免重复拼接 |
| `publish_time` | `publish_time` | 统一日期格式，无法解析时保留空值 |

`company` 和 `location` 在当前企业数据中不存在，应保留为空值，不从岗位描述中猜测。

## 5. 当前后端代码

| 文件 | 作用 | 当前状态 |
| --- | --- | --- |
| `scripts/dataset_adapter.py` | 将工作流 1 的三份 CSV 转为标准岗位和简历 JSONL | 已接入当前 `incoming` 数据 |
| `backend-src/app/services/chinese_bm25_service.py` | 创建索引、批量写入、字段加权检索 | 已切换到工作流 1 标准字段 |
| `backend-src/app/api/endpoints/bm25.py` | BM25 搜索和索引统计 API | 已注册 |
| `backend-src/scripts/index_chinese_jobs.py` | 标准岗位 JSONL 批量导入 Elasticsearch | 已指向 iteration 05 |
| `backend-src/scripts/search_chinese_jobs.py` | 命令行搜索测试 | 已验证 |
| `backend-src/scripts/retrieve_bm25_candidates.py` | 标准简历批量召回并输出候选集 | 已支持 Top1-Top200 |
| `scripts/evaluate_candidate_rankings.py` | 读取候选集和金标计算指标 | 已接入，等待金标 |
| `backend-src/app/main.py` | 注册 `/api/v1/bm25` 路由 | 已完成 |

当前 API：

- `POST /api/v1/bm25/search`
- `GET /api/v1/bm25/stats`

搜索请求示例：

```json
{
  "query": "后端开发 Python MySQL Redis",
  "size": 200,
  "source_type": "enterprise",
  "exclude_duplicates": true
}
```

注意：现有 API 返回完整岗位 `hits`，还需要增加面向队友的精简候选集输出。

## 6. BM25 基线配置

当前 `bigcompany_jobs_v1` baseline 配置：

| 字段 | 权重 |
| --- | ---: |
| `standard_job` | 7.0 |
| `title` | 6.0 |
| `job_family` | 6.0 |
| `skills` | 5.0 |
| `new_skills` | 4.5 |
| `requirements` | 3.0 |
| `responsibilities` | 2.5 |
| `domain_context` | 1.5 |
| `description` | 1.0 |
| `all_text` | 0.5 |

这组权重只是 baseline。最终权重应通过 Recall@100、Recall@200、MRR 和 NDCG 对比确定，不凭直觉直接定稿。

## 7. 查询文本设计

不要直接把完整简历全文交给 `multi_match`。历史实验中长中文文本会触发 Elasticsearch `maxClauseCount`，简单截取前 120 个字符虽然能跑通，但可能丢失核心技能。

建议构造专门的 `query_text_bm25`：

```text
目标岗位族 + 核心技能 + 工作年限 + 专业 + 关键项目词
```

例如：

```text
后端开发工程师 Python Java MySQL Redis Docker 5年 计算机科学
```

当前批量脚本从标准简历的 `target_job_family`、`skills`、工作角色、`major` 和 `years_experience` 中选取并去重，默认最多使用 30 个技能，而不是按字符硬截断。

## 8. 候选集输出契约

提供给其他工作流的最小输出：

```json
{
  "query_id": "resume_001",
  "candidates": [
    {
      "job_id": "JOB00001",
      "bm25_score": 12.34,
      "bm25_rank": 1
    }
  ]
}
```

批量结果建议使用 JSONL，每行对应一份简历。分数保留 Elasticsearch 原始 `_score`，不要提前归一化；后续融合模块可以基于每个查询单独归一化。

## 9. 当前运行状态

Elasticsearch 可以独立用 Docker 启动：

```powershell
docker compose up -d elasticsearch
```

健康检查：

```powershell
Invoke-RestMethod http://localhost:9200
```

生成工作流 1 标准文件：

```powershell
python .\scripts\dataset_adapter.py
```

Formal evaluation requires gold and silver label files by default. For smoke tests without labels only:

```powershell
python .\scripts\dataset_adapter.py --allow-missing-labels
```

重建岗位索引：

```powershell
python .\backend-src\scripts\index_chinese_jobs.py --recreate
```

批量召回 Top200：

```powershell
python .\backend-src\scripts\retrieve_bm25_candidates.py --size 200
```

2026-07-19 实测写入 `bigcompany_jobs_v1` 共 12,675 条，失败 0 条；单份简历 Top200 输出完整。生成物位于 `artifacts/`，默认不提交 Git。

## 10. 实施顺序

- [x] 保留 Elasticsearch BM25 服务。
- [x] 保留 FastAPI 搜索和统计接口。
- [x] 确认团队新岗位、词典和合成简历输入。
- [x] 新增大公司岗位 CSV -> 标准岗位 JSONL 适配器。
- [x] 更新 Elasticsearch mapping 和字段权重。
- [x] 更新索引脚本默认输入并加入字段校验。
- [x] 构造结构化 `query_text_bm25`。
- [x] 增加批量 Top100/Top200 候选集脚本。
- [x] 输出统一候选集 JSONL。
- [ ] 接入工作流 1 金标并完成 baseline 评估。
- [ ] 获取岗位 `standard_job` 到简历 `target_job_family` 的团队统一映射。
- [ ] 根据 dev 集结果优化岗位族加权和中文分词。
- [ ] 单独设计公务员岗位的检索字段和硬条件过滤。

## 11. 记录规范

- 代码变化使用小而明确的 Git commit，例如 `feat(bm25): support incoming job csv`。
- 当前可运行方式、字段和接口只更新本文件。
- 重要实验、故障和方案决策追加到 `markdown/trace.md`。
- 面向整个项目的阶段成果更新根目录 `CHANGELOG.md`。
