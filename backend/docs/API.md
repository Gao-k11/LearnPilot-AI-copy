# API 文档

启动后访问 Swagger：

`http://127.0.0.1:8001/docs`

## 健康检查

`GET /health`

返回服务状态和数据库连通状态。

## 课程与知识点

`GET /api/v1/courses`

查询课程列表。

`GET /api/v1/knowledge-points?course_id=1`

查询课程知识点。

## 学习画像

`POST /api/v1/profile/analyze`

请求示例：

```json
{
  "user_id": 1,
  "text": "我是软件工程大二学生，正在学习人工智能，CNN比较薄弱，目标是准备期末考试"
}
```

返回字段包含：`major`、`grade`、`course`、`goal`、`weak_points`、`preference`、`cognitive_style`、`knowledge_level`。

## 资源生成

`POST /api/v1/resources/generate`

支持资源类型：

`lecture`、`mind_map`、`exercise`、`reading`、`code_example`、`video_script`

请求示例：

```json
{
  "user_id": 1,
  "course_id": 1,
  "topic": "CNN",
  "weak_points": ["卷积", "池化"],
  "resource_types": ["lecture", "exercise", "code_example"]
}
```

## 学习路径规划

`POST /api/v1/paths/plan`

请求示例：

```json
{
  "user_id": 1,
  "course_id": 1,
  "goal": "准备人工智能期末考试",
  "weak_points": ["CNN", "反向传播"],
  "resource_ids": [1, 2]
}
```

## 智能辅导

`POST /api/v1/tutor/ask`

请求示例：

```json
{
  "user_id": 1,
  "question": "CNN里卷积核为什么能提取特征？",
  "history": []
}
```

## 学习效果评估

`POST /api/v1/evaluations/submit`

请求示例：

```json
{
  "user_id": 1,
  "path_id": 1,
  "correct_count": 8,
  "total_count": 10,
  "completed_resource_count": 3,
  "study_minutes": 120
}
```

## 一键学习流程

`POST /api/v1/learning/start`

该接口串联：

ProfileAgent -> DiagnosisAgent -> ResourceAgent -> ReviewAgent -> PlannerAgent

启用 LearnPilot-AI ML 服务后，`/api/v1/learning/start` 会优先调用 ML 服务 `/recommend`，并将返回的 `profile`、`recommendations`、`learning_path`、`generated_cards`、`agent_traces` 等结果映射为当前主后端响应结构；如果 ML 服务不可用，会自动回退到本地 Agent 流程。

请求示例：

```json
{
  "user_id": 1,
  "course_id": 1,
  "requirement": "我是软件工程大二学生，正在学习人工智能，CNN比较薄弱，目标是准备期末考试"
}
```

## 主后端与 ML 服务启动顺序

默认端口：

- LearnPilot-AI ML 服务：`http://127.0.0.1:8000`
- 当前主后端：`http://127.0.0.1:8001`

`.env` 配置：

```env
APP_PORT=8001
ML_SERVICE_URL=http://127.0.0.1:8000
USE_ML_SERVICE=true
```

启动顺序：

1. 启动 MySQL。
2. 启动 LearnPilot-AI ML 服务。
3. 启动当前主后端：

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8001
```
