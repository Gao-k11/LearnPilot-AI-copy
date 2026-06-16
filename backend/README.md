# Learning Agent Backend

## ML Compatibility APIs

The latest `path.js` and `builder.js` clients can use:

- `GET /api/ml/profile/current`
- `GET /api/ml/profile/questions`
- `POST /api/ml/profile/answer`
- `POST /api/ml/profile/generate`
- `POST /api/ml/learning-path/generate`

These endpoints reuse the existing profile extraction, profile persistence, and `/path/generate` logic. Bearer authentication is optional for demo usage; when present, the authenticated user takes priority over `userId`.

## Personalized Learning Paths

The `path.js` integration is available through:

- `GET /profile/schema`, `GET /profile/get`, and `POST /profile/update`
- `POST /path/generate`, `GET /path/detail`, `GET /path/list`, and `DELETE /path/delete`
- `POST /path/progress/update` and `GET /path/progress`
- `GET /path/resources`, `GET /path/recommend`, and `POST /path/feedback`

Path generation uses the existing ML path adapter when enabled and available, then falls back to local structured generation. Node resources reuse `resource_center`; document resources are exposed as `/resources/{id}/view`, while PPT and video resources keep their external URLs.

## Multi-Agent Producer

The `/producer` module provides synchronous multi-agent learning material generation for `producter.js`:

- `POST /producer/task` creates a completed generation task and persists its artifacts.
- `GET /producer/task/{task_id}` and `GET /producer/result/{task_id}` return task state and generated results.
- `POST /producer/chat` stores user and assistant messages.
- Roadmap, exercises, videos, code examples, and datasets have dedicated query endpoints.
- Video and reference generation first searches `resource_center`, then uses public fallback resources.
- `POST /producer/run` only simulates output. It never executes arbitrary user code.

Producer results include traces for requirement analysis, resource generation, exercise generation, code generation, and quality evaluation agents.

## Resource Center Opening Rules

The resource center exposes `GET /resources` and `GET /resources/{id}`.

- `document`: `open_type=content`, `url=""`. Open `detail_url` and render the complete Markdown `content` returned by the detail endpoint.
- `ppt` and `video`: `open_type=url`. Open the external `url`; `detail_url` remains available for metadata and detail display.
- Document resources never receive placeholder or fake URLs.

## Conversational Profile Builder

The frontend can build a learner profile through:

- `POST /profile-builder/start`
- `POST /profile-builder/answer`
- `GET /profile-builder/result?session_id=...`
- `POST /profile-builder/regenerate`

The six-round conversation collects major, grade, course, goal, weak points, learning preference, cognitive style, and knowledge level. Anonymous sessions are supported. When a valid Bearer token is supplied to the start endpoint, the completed result is also synchronized to `student_profile`.

基于大模型的个性化资源生成与学习多智能体系统后端。当前版本使用 FastAPI + MySQL，LLM 和 ML 能力先通过 Mock 适配器实现，后续可以直接替换 `backend/app/adapters/llm_adapter.py` 和 `backend/app/adapters/ml_adapter.py`。

## 目录结构

```text
backend/
  app/
    adapters/      # LLM/ML 预留适配器
    agents/        # Profile/Diagnosis/Retriever/Resource/Review/Planner/Tutor/Evaluator
    api/           # FastAPI 路由
    core/          # 配置和数据库连接
    models/        # SQLAlchemy ORM
    schemas/       # 请求响应模型
    services/      # 业务流程编排
mysql/             # 建表和初始化脚本
data/              # 知识库种子数据
generated/         # 生成结果预留目录
docs/              # 接口文档
```

## 运行步骤

1. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. 配置环境变量

```powershell
Copy-Item .env.example .env
```

打开 `.env`，把 `MYSQL_USER` 和 `MYSQL_PASSWORD` 改成你的 MySQL 账号密码。

3. 初始化数据库

```powershell
mysql -u root -p < mysql/01_create_tables.sql
mysql -u root -p < mysql/02_insert_init_data.sql
```

4. 启动后端

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8001
```

5. 打开接口页面

Swagger: `http://127.0.0.1:8001/docs`

健康检查: `http://127.0.0.1:8001/health`

如果 `/health` 返回：

```json
{
  "status": "ok",
  "database": true
}
```

说明服务和数据库连接正常。

## 核心流程

学生输入学习需求后，系统按以下流程运行：

ProfileAgent 分析学生画像 -> DiagnosisAgent 诊断薄弱知识点 -> RetrieverAgent 查询课程知识库 -> ResourceAgent 生成学习资源 -> ReviewAgent 审核内容 -> PlannerAgent 规划学习路径 -> TutorAgent 辅导问答 -> EvaluatorAgent 评估学习效果。

## 常用测试请求

一键生成画像、资源和学习路径：

```json
POST /api/v1/learning/start
{
  "user_id": 1,
  "course_id": 1,
  "requirement": "我是软件工程大二学生，正在学习人工智能，CNN比较薄弱，目标是准备期末考试"
}
```

接口详情见 [docs/API.md](docs/API.md)。

## LearnPilot-AI ML 服务

主后端现在支持调用 LearnPilot-AI 的 ML 服务。`/api/v1/learning/start` 的前端请求格式保持不变，后端内部会把数据库里的课程知识点、课程资源、历史画像和薄弱点转换为 ML `/recommend` 请求。

默认配置：

```env
APP_PORT=8001
ML_SERVICE_URL=http://127.0.0.1:8000
USE_ML_SERVICE=true
ML_SERVICE_TIMEOUT_SECONDS=15
```

推荐启动顺序：

1. 启动 MySQL，并执行 `mysql/01_create_tables.sql`、`mysql/02_insert_init_data.sql`。
2. 启动 LearnPilot-AI ML 服务，让它监听 `http://127.0.0.1:8000`。
3. 启动当前主后端：

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8001
```

对接数据流：

1. 查询 `student_profile`、`student_weakness`，生成 ML 所需的 `diagnostics`、`previous_mastery`、`goals`、`preferred_styles`。
2. 查询 `knowledge_point` 和 `course_resource`，转换成 ML 可排序、可 RAG 检索的 `knowledge_graph` 和 `resources`。
3. 调用 ML `/recommend`，把返回的 `profile`、`generated_cards/resources`、`learning_path` 映射并保存到后端表。
4. 当 ML 服务不可用时，主后端会自动回退到本地 Agent 流程；当 ML 只返回部分字段时，后端只补齐缺失资源或路径。

## Render 部署

本项目支持两种数据库模式：

```env
DATABASE_MODE=mysql
SQLITE_DATABASE_URL=sqlite:///./learning_agent_demo.db
```

本地开发默认使用 `DATABASE_MODE=mysql`，继续连接 MySQL，不影响现有开发流程。Render 云端演示推荐使用 `DATABASE_MODE=sqlite`，构建阶段会创建 SQLite 演示库并插入 demo 数据。

Render 部署文件：

```text
render.yaml
```

Render Web Service 配置要点：

```text
Root Directory: 当前后端目录
Build Command: pip install -r requirements.txt && python scripts/init_sqlite_demo.py
Start Command: uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

Render 环境变量：

```env
DATABASE_MODE=sqlite
SQLITE_DATABASE_URL=sqlite:///./learning_agent_demo.db
APP_ENV=production
APP_DEBUG=false
USE_ML_SERVICE=false
```

本地模拟 Render SQLite 演示模式：

```powershell
$env:DATABASE_MODE="sqlite"
$env:SQLITE_DATABASE_URL="sqlite:///./learning_agent_demo.db"
$env:USE_ML_SERVICE="false"
python scripts/init_sqlite_demo.py
uvicorn backend.app.main:app --host 0.0.0.0 --port 8001
```

部署后验证：

```text
/health
/docs
/openapi.json
/api/v1/learning/start
```

## 知识库素材导入

Markdown 知识库素材位于：

```text
data/knowledge_base/
```

导入到 MySQL 的 `course_resource` 表：

```powershell
python scripts/import_knowledge_base.py
```

脚本会读取 `data/knowledge_base/*.md`，将每个 Markdown 导入为课程资源，并额外生成一条复习卡片资源。`source` 字段写入 `markdown_import`；如果同名 `title` 已存在，则更新 `content`，不会重复插入。
