# JobMatch AI Docker容器化部署说明

## 1. 部署方式

本项目提供完整的`Dockerfile`和`docker-compose.yml`。评审人员可从公开GitHub仓库获取源码，在本机完成镜像构建与容器启动，不依赖私有镜像。

| 服务 | 容器名称 | 默认访问地址 | 作用 |
|---|---|---|---|
| 前端 | `jobmatch_frontend` | <http://localhost:18080> | 求职者端、企业端及动态图谱界面 |
| 后端 | `jobmatch_backend` | <http://localhost:18088> | REST API与业务处理服务 |
| Elasticsearch | `jobmatch_elasticsearch` | <http://localhost:9200> | 岗位检索与索引服务 |
| Neo4j | `jobmatch_neo4j` | <http://localhost:7474> | 岗位能力图谱服务 |

## 2. 环境要求

- Windows 10/11、macOS或主流Linux发行版；
- Docker Desktop或Docker Engine，支持`docker compose`；
- 建议至少8GB内存和10GB可用磁盘空间；
- 首次构建需要网络连接以下载基础镜像和依赖；
- 默认端口`18080`、`18088`、`9200`、`7474`和`7687`未被占用。

Windows用户应先启动Docker Desktop，并确认：

```powershell
docker --version
docker compose version
```

## 3. 获取代码与配置

```powershell
git clone https://github.com/HANYAODONG/job-hunt-ai.git
cd job-hunt-ai
Copy-Item .env.example .env
```

项目可在无大模型密钥的情况下启动，基础检索、图谱浏览和确定性链路仍可使用。需要启用DeepSeek增强能力时，在`.env`中填写：

```env
DEEPSEEK_API_KEY=替换为实际密钥
CAREER_ASSISTANT_API_KEY=替换为实际密钥
LLM_RESUME_API_KEY=替换为实际密钥
```

密钥只应保存在本机`.env`中，禁止提交到公开仓库。

## 4. 构建与启动

在仓库根目录执行：

```powershell
docker compose up -d --build
```

首次构建会下载Elasticsearch、Neo4j、Node.js和Python基础镜像并安装依赖。后续未修改依赖时会复用Docker缓存。

```powershell
docker compose ps
```

正常情况下四个容器均为`Up`，后端、Elasticsearch和Neo4j显示`healthy`。随后访问<http://localhost:18080>。

## 5. 部署验证

```powershell
Invoke-RestMethod http://localhost:18088/health
Invoke-WebRequest http://localhost:18080 -UseBasicParsing
docker compose logs --tail 100 backend
docker compose logs --tail 100 frontend
```

Swagger接口文档：<http://localhost:18088/docs>。

## 6. 演示数据验证

企业端“岗位演化中心”支持导入月度JD。新岗位发现演示文件位于：

```text
artifacts/discovery_synthetic_fixture/synthetic_new_role_jds.csv
```

进入“企业端 -> 岗位演化中心 -> 批量新岗位发现”，点击“导入月度JD”，导入后选择`2026-08`并点击“验证新岗位发现”。样例包含12条同类JD，用于演示候选新岗位聚类、来源证据保留和人工审核机制。

Docker演示环境默认使用离线词法路由，避免临时下载文本向量模型。如已准备好模型，可在`.env`中设置：

```env
JOB_UPDATE_SIMILARITY_MODE=semantic
JOB_UPDATE_TEXT2VEC_MODEL=本地模型目录或模型名称
```

## 7. 启动、停止与重建

```powershell
# 再次启动
docker compose up -d

# 停止并保留数据库卷
docker compose down

# 源码或依赖更新后重新构建
docker compose up -d --build
```

仅在确认不需要现有Elasticsearch和Neo4j数据时执行：

```powershell
docker compose down -v
```

## 8. 常见问题

端口冲突时，在`.env`中修改：

```env
FRONTEND_PORT=18081
BACKEND_PORT=18089
```

容器未就绪时执行：

```powershell
docker compose ps
docker compose logs --tail 200 backend
```

修改源码后页面未变化时执行：

```powershell
docker compose up -d --build --force-recreate backend frontend
```

随后在浏览器按`Ctrl + F5`强制刷新。一般不要删除数据卷，以免清除已建立的索引和图谱数据。
