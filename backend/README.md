# Learning Agent Backend

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

主后端现在支持调用 LearnPilot-AI 的 ML 服务。默认配置：

```env
APP_PORT=8001
ML_SERVICE_URL=http://127.0.0.1:8000
USE_ML_SERVICE=true
```

推荐启动顺序：

1. 启动 MySQL，并执行 `mysql/01_create_tables.sql`、`mysql/02_insert_init_data.sql`。
2. 启动 LearnPilot-AI ML 服务，让它监听 `http://127.0.0.1:8000`。
3. 启动当前主后端：

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8001
```

当 ML 服务不可用时，主后端会自动回退到本地 Mock MLAdapter，现有接口仍可正常调用。

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
