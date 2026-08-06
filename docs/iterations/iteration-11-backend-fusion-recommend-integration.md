# 第十一次迭代：后端统一推荐接口与融合链路收口

## 迭代原因

项目已经进入后期整合阶段。当前 BM25、语义重排、技能/知识图谱特征、融合排序和前端页面都已经有了各自实现，但前端如果分别调用多个模块接口，会导致对接复杂、异常处理困难，也不利于演示。

因此本轮优先把后端收口成一个前端可直接调用的统一推荐入口。

## 迭代目的

本次迭代目标是：

```text
前端只调用一个接口
  -> 后端负责组织推荐链路
  -> 返回 TopN 推荐、分项得分和解释
```

这样前端可以先完成真实接口对接，后端内部再逐步把 sample、offline、online 三种链路替换成更完整的真实产物。

## 本次修改

### 1. 新增统一推荐接口

新增接口：

```text
POST /api/v1/fusion/recommend
```

请求示例：

```json
{
  "candidate_id": "resume_000001_exp00_0",
  "top_k": 10,
  "candidate_pool": 100,
  "mode": "sample"
}
```

也支持自由文本：

```json
{
  "query_text": "熟悉 Python、SQL，有后端开发和数据处理经验",
  "top_k": 10,
  "mode": "sample"
}
```

返回内容保持和融合排序统一：

```json
{
  "query_id": "resume_000001_exp00_0",
  "results": [
    {
      "job_id": "JOB00001",
      "final_score": 0.82,
      "rank": 1,
      "score_breakdown": {
        "bm25_score": 0.91,
        "semantic_score": 0.74,
        "skill_coverage": 0.45,
        "job_family_match": 1.0,
        "graph_relatedness": 0.38
      },
      "explanation": {
        "matched_skills": ["python", "sql"],
        "missing_skills": ["pytorch"],
        "reason": "该岗位与您的简历匹配度良好..."
      },
      "meta": {
        "title": "后端开发工程师",
        "company": "示例公司",
        "location": "北京",
        "source_type": "enterprise"
      }
    }
  ]
}
```

### 2. 支持四种推荐模式

`/recommend` 支持：

```text
auto    默认模式，优先在线，失败后回退到离线或 sample
online  调 Elasticsearch BM25 后融合
offline 读取 artifacts/fusion_ranking/ 下的预计算融合结果
sample  读取 dataset_iteration_05/sample_pack 即时生成完整推荐结果
mock    使用服务端 mock 数据
```

当前前后端联调建议优先使用：

```text
mode = sample
```

这样不依赖完整 ES 索引、embedding 文件和 Neo4j 图谱，能先把页面和接口打通。

### 3. 修复 artifacts 路径选择问题

原逻辑只要 `artifacts/fusion_ranking` 不存在，就会把整个 artifacts 路径切到 `/app/artifacts`。

这会导致本地明明已经生成：

```text
artifacts/dataset_iteration_05/
```

但由于还没有：

```text
artifacts/fusion_ranking/
```

后端反而读不到本地 sample 数据。

本次修改为分别判断：

```text
fusion_ranking 路径单独判断
dataset_iteration_05 路径单独判断
```

这样 sample 联调更稳定。

### 4. 调整分层融合默认门控

之前分层融合中：

```text
family_discount = 1.0
```

这意味着岗位族不匹配时没有任何降权效果。

本次调整为：

```text
family_discount = 0.85
```

即岗位族不一致时先温和降权，不直接过滤，避免岗位族识别错误造成误杀。

### 5. 修复前端岗位元数据透传

融合输入中 `_meta` 用于携带岗位标题、公司、地点、薪资等前端展示信息。之前读取方式不够稳，本次改为从 Pydantic `model_extra` 中读取，确保 `FusionOutput.meta` 能正常返回给前端。

## 验证情况

已完成：

```powershell
python -m py_compile backend-src/app/api/endpoints/fusion.py backend-src/app/services/fusion_scoring_service.py
python -m py_compile backend-src/app/**/*.py
python .\scripts\dataset_adapter.py
```

结果：

```text
后端 app Python 文件语法编译通过
dataset_iteration_05 可重新生成
```

当前本地 Python 环境未安装 FastAPI，因此还未做函数级接口调用测试。下一步建议通过 Docker 启动后，在 `/docs` 或 PowerShell 中测试：

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:18088/api/v1/fusion/recommend" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"candidate_id":"resume_000001_exp00_0","top_k":10,"candidate_pool":50,"mode":"sample"}'
```

## 对前端的影响

前端下一步优先对接：

```text
POST /api/v1/fusion/recommend
```

不建议前端直接分别调用 BM25、semantic、KG、fusion 多个接口。前端只需要处理统一返回：

- `results`
- `final_score`
- `score_breakdown`
- `explanation`
- `meta`

这样后端内部链路之后继续升级，不会频繁影响前端。

## 后续任务

1. Docker 启动后测试 `/api/v1/fusion/recommend`。
2. 前端推荐页面接入该接口。
3. sample 模式通过后，再接 offline 预计算融合结果。
4. 最后再接 online 模式：真实 BM25、真实 semantic、真实 KG features。
5. 输出一份 sample 全链路运行记录和初步评估结果。
