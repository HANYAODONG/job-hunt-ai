# JobMatch AI 部署测试与问题修复记录

记录日期：2026-07-10

本文档记录本轮本地部署、联调测试中遇到的问题、定位结果、源码修复方式和当前推荐启动流程。当前测试结论：系统可以完成登录注册、搜索、简历上传和投递流程。

## 当前可用状态

服务地址：

```text
Frontend: http://localhost:18080
Backend API: http://localhost:8000
API Docs: http://localhost:8000/docs
Elasticsearch: http://localhost:9200
Neo4j Browser: http://localhost:7474
```

Neo4j 登录：

```text
Username: neo4j
Password: password
```

当前前端端口使用 `18080`，原因是本机 Windows 对 `3001/3002` 端口绑定有限制。配置位置：

```text
.env
FRONTEND_PORT=18080
```

## 推荐启动流程

在 PowerShell 中执行：

```powershell
cd "D:\Desktop\挑战杯大模型组\job-hunt-ai-main"
docker compose down
docker compose up -d --build
```

查看容器状态：

```powershell
docker compose ps
```

如果四个服务都正常，再打开：

```text
http://localhost:18080
```

如果岗位数据为空，导入样例数据：

```powershell
.\scripts\import-sample-data.ps1
```

## 已修复问题

### 1. `install.ps1` 中 `docker compose` 调用失败

现象：

```text
无法将“docker compose”项识别为 cmdlet、函数、脚本文件或可运行程序的名称
```

原因：PowerShell 不能把 `"docker compose"` 当成单个可执行文件调用。

修复：将命令和参数拆开：

```powershell
$DockerCompose = "docker"
$DockerComposeArgs = @("compose")
& $DockerCompose @DockerComposeArgs build
& $DockerCompose @DockerComposeArgs up -d
```

同时将安装脚本输出改成纯 ASCII，避免 PowerShell 显示乱码。

### 2. 注册失败：`bcrypt` 与 `passlib` 不兼容

现象：注册页提示失败，后端日志出现：

```text
password cannot be longer than 72 bytes
AttributeError: module 'bcrypt' has no attribute '__about__'
```

原因：`bcrypt 5.x` 与当前 `passlib` 组合存在兼容问题。

修复：在 `backend-src/requirements.txt` 固定版本：

```text
bcrypt>=4.0.0,<5.0.0
```

### 3. 登录后右上角仍显示 Login / Sign Up

现象：登录成功跳回首页后，Header 仍显示未登录。

原因：登录页只写入了 `localStorage`，没有更新 `AuthContext` 的 React 状态。

修复：`frontend-src/src/pages/LoginPage.js` 中改为调用：

```javascript
login(response.access_token, response.user);
navigate('/');
```

### 4. 注册/登录错误提示过于笼统

现象：前端只显示通用错误，难以判断真实后端错误。

修复：`LoginPage.js` 和 `RegisterPage.js` 改为优先展示 `err.message`，便于调试。

### 5. 搜索页示例提示词第一次点击弹出空查询提示

现象：点击示例卡片后先弹出：

```text
Please enter a search query
```

原因：示例点击逻辑先 `setSearchQuery(...)` 再立即 `handleSearch()`，React 状态更新尚未完成，搜索函数读到旧的空字符串。

修复：`SearchPage.js` 中新增 `handleExampleQuery(query)`，并让 `handleSearch(queryOverride)` 支持传入查询文本。

### 6. 搜索 0 结果

现象：系统部署成功但搜索为空。

原因：Elasticsearch 初始没有岗位数据。

修复：新增样例数据导入脚本：

```text
scripts/import-sample-data.ps1
```

该脚本会调用后端 CSV 导入接口导入：

```text
jobs/SDE-Nov21.csv
```

### 7. 前端仍显示 Demo Mode / Mock Data

现象：搜索有结果，但页面提示：

```text
Demo Mode - Using Mock Data
```

原因：

1. `docker-compose.yml` 中原来配置的是 `BACKEND_URL`，但 React 实际读取 `REACT_APP_API_URL`。
2. 前端接口层在后端不可用或超时时会自动降级到 mock 数据，容易误导测试。

修复：

```yaml
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_USE_MOCK_DATA=false
```

同时将前端 API 超时时间从 30 秒提高到 120 秒。默认不再启用 mock 降级。

### 8. 前端端口 `3001/3002` 无法绑定

现象：

```text
ports are not available
listen tcp 0.0.0.0:3001: bind: An attempt was made to access a socket in a way forbidden by its access permissions
```

原因：Windows/Hyper-V/WSL 可能保留了相关端口。

修复：`docker-compose.yml` 支持从环境变量读取前端端口：

```yaml
ports:
  - "${FRONTEND_PORT:-3001}:3000"
```

当前 `.env` 固定为：

```text
FRONTEND_PORT=18080
```

### 9. 后端首次启动加载模型较慢，被 Docker 误判 unhealthy

现象：`docker compose up -d --build frontend` 时提示：

```text
dependency failed to start: container jobmatch_backend is unhealthy
```

原因：本地构建版后端首次启动需要加载模型和初始化服务，原健康检查等待时间偏短。

修复：放宽后端 healthcheck：

```yaml
retries: 10
start_period: 180s
```

## 仍需优化的问题

### 1. CSV 导入较慢

当前 CSV 导入会写 Elasticsearch 和 Neo4j，处理时间较长。建议后续改为：

```text
上传接口快速返回 task_id
后台任务处理导入
提供任务进度查询接口
Elasticsearch 使用 bulk API
Neo4j 使用 UNWIND 批量写入
```

### 2. 搜索接口响应仍偏慢

导入样例数据后，部分搜索请求仍可能耗时较长。建议增加分阶段耗时日志：

```text
query parsing
embedding
Elasticsearch retrieval
Neo4j retrieval
fusion / reranking
LLM explanation
```

### 3. NLTK 数据下载被网络安全策略拦截

后端日志中可能出现：

```text
Error loading punkt
Error loading stopwords
```

目前不影响核心流程。后续建议将 NLTK 数据预置到镜像，避免容器启动时联网下载。

### 4. Neo4j 图谱结构仍需和挑战杯任务对齐

当前图谱更接近 JobMatchAI 原论文 Demo，后续应扩展为挑战杯赛题所需方向：

```text
岗位-技能-时间动态图谱
新兴岗位发现
岗位能力演化分析
技能迁移路径分析
```

## 本轮修改文件

```text
backend-src/requirements.txt
docker-compose.yml
.env
install.ps1
scripts/import-sample-data.ps1
frontend-src/src/pages/LoginPage.js
frontend-src/src/pages/RegisterPage.js
frontend-src/src/pages/SearchPage.js
frontend-src/src/services/api.js
docs/deployment-issues.md
```

## 当前结论

本轮目标从“能不能部署”推进到“源码层面修复已知阻塞问题”。当前系统已经可以用于基础演示和后续算法/大模型组二次开发，但性能、图谱初始化、异步导入和挑战杯任务特化仍需要继续推进。
