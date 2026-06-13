# LearnPilot-AI

LearnPilot-AI 是面向“中国软件杯”A3 赛题“基于大模型的个性化资源生成与学习多智能体系统开发”的原型项目。项目围绕学习诊断、学生画像、资源推荐、学习路径规划、RAG 个性化内容生成和学习反馈闭环，构建一个可解释、可演示、可继续扩展的智能学习服务。

当前仓库包含主后端 `backend/` 与 ML 服务 `ml/` 两部分。前端调用主后端业务接口，主后端会把数据库中的课程、知识点、课程资源和学生历史画像转换为 ML 请求，再由 ML 服务完成推荐、路径规划、RAG 学习卡生成和质量评估。

## 项目目标

在传统在线学习系统中，学习资源往往以固定目录或人工标签组织，难以根据学生的真实掌握情况动态调整。LearnPilot-AI 的目标是利用大模型和多智能体协作能力，把“测评诊断、学习画像、资源匹配、路径规划、内容生成、反馈更新”串成闭环，为不同基础、目标和偏好的学生生成个性化学习方案。

系统重点解决以下问题：

- 如何根据测评结果和学习行为识别知识薄弱点。
- 如何把学生目标、学习偏好、行为反馈融合为动态学习画像。
- 如何从资源库中推荐难度合适、形式匹配、覆盖薄弱点的学习资源。
- 如何基于知识图谱和先修关系规划阶段化学习路径。
- 如何通过 RAG 生成个性化讲解、练习、错因分析和复习建议。
- 如何在学生学习后更新画像，并重新调整推荐与路径。

## 核心功能

| 功能模块 | 说明 |
| --- | --- |
| 学习诊断 | 输入知识点测评分数，归一化为掌握度，并识别薄弱点 |
| 学生画像 | 融合诊断、学习目标、偏好、行为日志和历史状态，生成动态画像 |
| 资源推荐 | 根据薄弱点匹配、难度匹配、学习形式偏好、资源质量和时长进行排序 |
| 路径规划 | 基于知识图谱和先修关系，生成从基础到综合应用的学习路径 |
| RAG 内容生成 | 检索相关课程资源证据，调用 qwen3.7-plus 或模板 fallback 生成学习卡片 |
| 多智能体协作 | 输出诊断、画像、推荐、规划、生成与评估 Agent 的执行 trace |
| 反馈闭环 | 根据学习反馈更新掌握度，展示反馈前后路径和画像变化 |
| 离线评估 | 支持 Recall@K、NDCG@K 和掌握度提升示例评估 |

## 系统架构

```text
学生测评/行为日志/学习目标
        |
        v
诊断 Agent
  - 知识点掌握度
  - 薄弱点识别
        |
        v
画像 Agent
  - 动态学生画像
  - 风险等级
  - 学习偏好
        |
        +--------------------+
        |                    |
        v                    v
推荐 Agent              规划 Agent
  - 资源排序              - 知识图谱
  - 推荐理由              - 先修关系
        |                    |
        +----------+---------+
                   |
                   v
生成与评估 Agent
  - RAG 资源检索
  - 个性化学习卡
  - 内容质量检查
                   |
                   v
学习反馈闭环
  - 更新画像
  - 调整推荐
  - 重规划路径
```

## 技术实现

当前版本以轻量、可解释的规则和数据结构实现核心闭环，便于比赛演示和后续接入真实大模型。

- 后端接口：FastAPI
- 核心语言：Python
- 数据建模：dataclass + Pydantic
- 推荐策略：可解释加权排序 + 多样性重排
- 路径规划：知识图谱先修依赖 + 掌握度缺口排序
- RAG 原型：资源内容切片 + BM25/TF-IDF 融合检索 + qwen3.7-plus 生成 + 质量检查
- 测试方式：unittest

推荐排序当前采用如下可解释公式：

```text
score = 0.42 * 薄弱点匹配
      + 0.24 * 难度匹配
      + 0.14 * 形式偏好
      + 0.14 * 资源质量
      + 0.06 * 时长适配
```

## 目录结构

```text
LearnPilot-AI/
  README.md
  backend/              主后端服务、数据库模型、业务 API 和 ML 对接层
  ml/
    data/                 样例反馈数据
    docs/                 ML 设计文档
    scripts/              演示、评估和 API 启动脚本
    src/ml_service/       ML 服务源码
    tests/                单元测试
    requirements.txt      API 运行依赖
    README.md             ML 模块说明
```

## 快速开始

### 1. 创建 conda 沙箱

```powershell
conda env create -f environment.yml
conda activate learnpilot-ai
```

如依赖变化，可更新环境：

```powershell
conda env update -f environment.yml --prune
```

可选安装高级排序依赖：

```powershell
pip install -r ml/requirements-advanced.txt
```

### 2. 运行单元测试

```powershell
python -m unittest discover -s ml/tests
```

### 3. 运行命令行演示

```powershell
python ml/scripts/demo.py
```

脚本会输出一次完整学习闭环结果，包括学生画像、推荐资源、学习路径、生成学习卡和多智能体 trace。

### 4. 运行离线评估

```powershell
python ml/scripts/evaluate.py
```

评估脚本会基于 `ml/data/sample_feedback.json` 输出 `Recall@5`、`NDCG@5`、推荐明细和掌握度提升示例。

完整 ML 2.0 流程：

```powershell
python ml/scripts/generate_synthetic_data.py
python ml/scripts/train_ranker.py
python ml/scripts/evaluate.py
python ml/scripts/demo.py
```

### 5. 启动 API 服务

```powershell
uvicorn ml_service.api:app --app-dir ml/src --reload --port 8000
```

启用 qwen3.7-plus 真实生成前，请复制 `.env.example` 为 `.env` 或 `ml/.env`，再填入自己的 DashScope API Key。未配置 `.env` 时系统会自动使用模板生成，测试和离线演示不受影响。

```powershell
Copy-Item .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
python ml/scripts/qwen_smoke_test.py
```

Windows 也可以使用项目脚本：

```powershell
powershell -ExecutionPolicy Bypass -File ml/scripts/run_api.ps1 -Port 8000
```

健康检查：

```text
GET http://127.0.0.1:8000/health
```

### 6. 双服务联调

后端对外接口保持 `/api/v1/learning/start` 不变。启用 ML 后，主后端会查询 `knowledge_point`、`course_resource`、`student_profile`、`student_weakness`，把真实课程资源传给 ML `/recommend`，再把 ML 返回的画像、资源和路径保存回后端数据库。

```powershell
# 终端 1：启动 ML 服务
uvicorn ml_service.api:app --app-dir ml/src --reload --port 8000

# 终端 2：启动主后端
cd backend
$env:ML_SERVICE_URL="http://127.0.0.1:8000"
$env:USE_ML_SERVICE="true"
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8001
```

联调请求：

```text
POST http://127.0.0.1:8001/api/v1/learning/start
```

如果 ML 服务未启动、超时或大模型不可用，主后端会自动回退到本地 Agent 流程；如果只是 ML 返回了部分字段，后端只补齐缺失的资源或路径，不会丢弃已返回的 ML 结果。

## API 说明

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/health` | GET | 服务健康检查 |
| `/demo-cases` | GET | 获取内置演示学生样例 |
| `/train/status` | GET | 获取当前排序模型和 fallback 状态 |
| `/evaluate` | GET | 运行内置 ML 指标评估 |
| `/diagnose` | POST | 输入测评答案，输出知识点诊断结果 |
| `/recommend` | POST | 输出画像、推荐、路径、学习卡和 Agent trace |
| `/path` | POST | 输出学习路径和知识图谱 |
| `/generate` | POST | 输出 RAG 个性化学习卡 |
| `/feedback` | POST | 输入学习反馈，输出反馈前后变化 |
| `/student/update-profile` | POST | 输入历史画像和新事件，输出更新画像 |

请求示例：

```json
{
  "student": {
    "student_id": "stu_001",
    "goals": ["两周内完成 Python 入门项目"],
    "preferred_styles": ["example", "quiz"],
    "diagnostics": {
      "变量": 0.9,
      "条件判断": 0.62,
      "循环": 0.42,
      "函数": 0.35,
      "列表": 0.4
    },
    "events": [
      {
        "resource_id": "r003",
        "knowledge_points": ["循环"],
        "score": 0.5,
        "completed": true,
        "dwell_seconds": 720,
        "liked": true
      }
    ]
  },
  "top_k": 5
}
```

响应会包含：

- `profile`：学生画像、目标难度、风险等级、薄弱点、投入度、稳定性和遗忘风险。
- `recommendations`：推荐资源、分数和推荐理由。
- `learning_path`：阶段化学习路径。
- `generated_cards`：基于检索资源生成的个性化学习卡。
- `model_meta`：排序模型类型、特征版本、训练指标和 fallback 状态。
- `retrieval_evidence`：RAG 检索证据。
- `generation_quality`：生成质量分。
- `counterfactual_explanations`：反事实推荐解释。
- `knowledge_graph`：知识图谱节点及当前掌握度。
- `agent_traces`：多智能体执行过程。

## 演示场景

以 Python 入门学习为例，系统内置了变量、条件判断、循环、函数、列表、项目实践等知识点，以及视频、例题、测验、文本、项目等不同形式的资源。

当学生在“循环、函数、列表”等知识点掌握度较低时，系统会：

1. 识别薄弱知识点并生成风险等级。
2. 推荐难度适中、形式偏好的资源。
3. 根据变量、条件判断、循环、函数、列表、项目实践之间的先修关系规划路径。
4. 为优先学习步骤生成讲解、例子、练习和复习提示。
5. 在学生完成资源并提交反馈后，更新掌握度并调整后续路径。

## 项目亮点

- 闭环完整：覆盖诊断、画像、推荐、规划、生成、反馈再规划全过程。
- 多智能体可解释：每个 Agent 都返回 action 和 output，便于前端展示和评委理解。
- 推荐理由透明：每条推荐都带有排序原因，降低黑盒感。
- 知识图谱驱动：路径规划考虑先修关系，不只按薄弱点简单排序。
- 可扩展大模型：当前生成模块为可运行原型，后续可替换为真实 LLM 和向量检索。
- 工程可验证：提供单元测试、演示脚本和包含 Recall、NDCG、路径合理性、生成质量、多样性指标的离线评估脚本。

## 后续规划

- 接入真实课程资源库和题库，扩大知识点与资源覆盖范围。
- 使用向量数据库实现语义检索，提升 RAG 召回质量。
- 接入真实大模型，生成更自然的个性化讲解和练习。
- 引入知识追踪模型，如 DKT 或 SAKT，刻画学生长期掌握变化。
- 在交互数据充足后，将规则排序升级为 Learning-to-Rank、LightGBM 或双塔召回模型。
- 增加前端可视化页面，展示学生画像、知识图谱、推荐理由和 Agent 协作过程。

## 相关文档

- ML 模块说明：`ml/README.md`
- ML 设计文档：`ml/docs/ml_design.md`
