# API 文档

启动后访问 Swagger：

`http://127.0.0.1:8001/docs`

## ML Compatibility APIs

- `GET /api/ml/profile/current?userId=1` returns the latest profile or a default profile.
- `GET /api/ml/profile/questions` returns the six builder question definitions.
- `POST /api/ml/profile/answer` stores one answer and optional batched answers under an automatically generated or supplied session ID.
- `POST /api/ml/profile/generate` extracts and persists an eight-field learner profile.
- `POST /api/ml/learning-path/generate` delegates to the existing personalized path generator.

When an Authorization Bearer token is supplied, its user ID takes priority. Without authentication or `userId`, demo endpoints default to user ID `1`.

## Personalized Profile And Path

Profile endpoints:

- `GET /profile/schema`
- `GET /profile/get?userId=1`
- `POST /profile/update`

`POST /profile/update` accepts a `userId` and a `profile` object. It updates the latest `student_profile` record or creates one when needed.

Path endpoints:

- `POST /path/generate`
- `GET /path/detail?pathId=1`
- `GET /path/list?userId=1`
- `DELETE /path/delete?pathId=1`
- `POST /path/progress/update`
- `GET /path/progress?pathId=1`
- `GET /path/resources?nodeId=1`
- `GET /path/recommend?userId=1`
- `POST /path/feedback`

Path and node responses expose camelCase `pathId` and `nodeId`, with numeric `path_id` and `node_id` compatibility fields. Path generation tries the configured ML path service first and falls back to local generation.

Document recommendations use:

```json
{
  "open_type": "url",
  "url": "/resources/7/view",
  "detail_url": "/resources/7"
}
```

`GET /resources/{id}/view` returns the complete resource detail and Markdown content while incrementing the view count.

## Multi-Agent Producer

`POST /producer/task`

```json
{
  "topic": "CNN",
  "requirement": "生成适合大二学生的学习资源",
  "types": ["lecture", "mind_map", "exercise", "video", "code"]
}
```

The task is completed synchronously and persisted to `producer_task` and `producer_artifact`. Its result includes `lecture`, `mind_map`, `exercises`, `reading`, `videos`, `code_examples`, `datasets`, `roadmap`, reused resource-center references, and five `agent_traces`.

`GET /producer/task/{task_id}`

Returns status, progress, and timestamps.

`GET /producer/result/{task_id}`

Returns the persisted multi-agent generation result.

`POST /producer/chat`

```json
{
  "session_id": "",
  "message": "什么是 CNN？",
  "topic": "CNN"
}
```

The session ID is optional. User and assistant messages are persisted.

Additional endpoints:

- `GET /producer/roadmap?topic=CNN`
- `GET /producer/exercises?topic=CNN`
- `GET /producer/videos?topic=CNN`
- `GET /producer/code?topic=CNN&language=python`
- `GET /producer/datasets?keyword=CNN`

`POST /producer/run`

```json
{
  "language": "python",
  "code": "print('hello')"
}
```

This endpoint performs static parsing and returns simulated output. It never executes submitted code.

## Resource Center

`GET /resources`

Each list item includes `open_type`, `detail_url`, and `url`.

- For `document`, `open_type` is `content`, `url` is an empty string, and `detail_url` is `/resources/{id}`.
- For `ppt` and `video`, `open_type` is `url`, and `url` contains the external courseware or video address.

`GET /resources/{id}`

Returns the full resource detail. A document response includes the complete Markdown `content`, which the frontend should render on its detail page. PPT and video resources should be opened through `url`.

`POST /resources/{id}/view`

Increments and returns the latest view count.

`POST /resources/{id}/like`

Increments and returns the latest like count.

## Profile Builder

`POST /profile-builder/start`

Creates an anonymous or authenticated profile-building session and returns the first question.

`POST /profile-builder/answer`

```json
{
  "session_id": "session-id",
  "answer": "我是软件工程大二学生，正在学习人工智能。"
}
```

Continue submitting answers until `finished` becomes `true`. The conversation collects `major`, `grade`, `course`, `goal`, `weak_points`, `preference`, `cognitive_style`, and `knowledge_level`.

`GET /profile-builder/result?session_id=session-id`

Returns the current or completed profile for the session.

`POST /profile-builder/regenerate`

```json
{
  "session_id": "session-id"
}
```

Rebuilds the profile from all existing user answers. If the session was started with a valid Bearer token, the completed profile is also synchronized to `student_profile`.

## 健康检查

`GET /health`

返回服务状态、数据库、ML 服务、Redis、Qwen 配置状态。

## 认证

`POST /api/v1/auth/register`

```json
{
  "username": "teacher1",
  "password": "secret123",
  "display_name": "教师一",
  "role": "teacher"
}
```

`POST /api/v1/auth/login`

```json
{
  "username": "teacher1",
  "password": "secret123"
}
```

`GET /api/v1/auth/me`

写入类接口建议携带：

```text
Authorization: Bearer <access_token>
```

## 课程与知识点

`GET /api/v1/courses`

查询课程列表。

`GET /api/v1/knowledge-points?course_id=1`

查询课程知识点。

`POST /api/v1/courses/{course_id}/resources/import`

教师或管理员导入课程资料。支持 `markdown`、`pdf_text`、`question_json`、`mistake_json`。导入会写入课程资源、资源切片或题库。

```json
{
  "filename": "cnn.md",
  "source_type": "markdown",
  "content": "# CNN 入门\nCNN 包含卷积、池化和特征图。"
}
```

`GET /api/v1/import-jobs/{job_id}`

查询导入任务状态。

`GET /api/v1/courses/{course_id}/resources`

查询课程资源。

`GET /api/v1/courses/{course_id}/questions`

查询课程题库。

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

响应包含 `answer`、`hints`、`next_action`，若命中课程切片，还会包含 `evidence`。

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

提交后会写入反馈事件，并在 ML 服务可用时调用 `/feedback` 更新画像和路径调整摘要。

## 一键学习流程

`POST /api/v1/learning/start`

该接口串联：

ProfileAgent -> DiagnosisAgent -> ResourceAgent -> ReviewAgent -> PlannerAgent

启用 LearnPilot-AI ML 服务后，`/api/v1/learning/start` 会优先调用 ML 服务 `/recommend`。前端请求结构不变，主后端会自动查询 `student_profile`、`student_weakness`、`knowledge_point`、`course_resource`，并转换为 ML 所需的 `student`、`resources`、`knowledge_graph` 和 `course_context`。

ML 返回的 `profile`、`recommendations`、`learning_path`、`generated_cards/resources`、`agent_traces` 会被映射为当前主后端响应结构并落库；如果 ML 服务不可用，会自动回退到本地 Agent 流程。如果 ML 只返回部分字段，后端只补齐缺失资源或路径，不会丢弃已返回的 ML 结果。

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
ML_SERVICE_TIMEOUT_SECONDS=15
```

启动顺序：

1. 启动 MySQL。
2. 启动 LearnPilot-AI ML 服务。
3. 启动当前主后端：

```powershell
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8001
```

联调验证：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8001/api/v1/learning/start `
  -ContentType "application/json" `
  -Body '{"user_id":1,"course_id":1,"requirement":"我是软件工程大二学生，CNN比较薄弱，想准备期末考试"}'
```

响应中的资源应来自后端 `course_resource` 经过 ML 推荐/生成后的结果，而不是 ML 默认 Python demo 数据。

## Docker 生产部署

推荐使用根目录 `docker-compose.yml`：

```powershell
Copy-Item .env.production.example .env
docker compose up --build
```

服务：

- `backend`: `http://127.0.0.1:8001`
- `ml-service`: `http://127.0.0.1:8000`
- `mysql`: `3306`
- `redis`: `6379`
- `worker`: RQ worker，用于导入、训练、批处理等长任务扩展。
