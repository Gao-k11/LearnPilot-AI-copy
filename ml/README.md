# 知行星图 ML 服务

本目录只包含项目的 ML 部分代码，用于支撑“基于大模型的个性化资源生成与学习多智能体系统”的学习闭环能力。

## 能力范围

- 学习诊断：根据测评答案输出知识点掌握度和薄弱点。
- 学习画像：融合诊断结果、行为日志、目标和偏好，生成学生画像。
- 资源推荐：结合薄弱点、难度匹配、学习风格、资源质量和多样性进行排序。
- 路径规划：基于知识图谱和先修关系生成阶段化学习路径。
- RAG 生成：检索课程资源后生成个性化讲解、例子、练习和复习建议。
- 多智能体 trace：输出诊断、画像、推荐、规划、生成与评估 5 个 Agent 的执行过程。
- 反馈闭环：输入学习反馈后更新画像，并重新生成推荐和学习路径。

## 目录结构

```text
ml/
  data/                 样例反馈数据
  docs/                 ML 设计说明
  scripts/              demo、评估和 API 启动脚本
  src/ml_service/       ML 服务源码
  tests/                单元测试
  requirements.txt      API 运行依赖
```

## 快速验证

核心逻辑不依赖 FastAPI，直接运行：

```powershell
python -m unittest discover -s ml/tests
python ml/scripts/demo.py
python ml/scripts/evaluate.py
```

## 启动 API

```powershell
pip install -r ml/requirements.txt
uvicorn ml_service.api:app --app-dir ml/src --reload --port 8000
```

Windows 也可以使用脚本：

```powershell
powershell -ExecutionPolicy Bypass -File ml/scripts/run_api.ps1 -Port 8000
```

健康检查：

```text
GET http://127.0.0.1:8000/health
```

## API 概览

| 接口 | 作用 |
| --- | --- |
| `GET /health` | 服务健康检查 |
| `GET /demo-cases` | 返回 3 个固定演示学生 |
| `POST /diagnose` | 输入测评答案，输出诊断结果 |
| `POST /recommend` | 输出画像、推荐、路径、学习卡和 Agent trace |
| `POST /path` | 输出学习路径和知识图谱 |
| `POST /generate` | 输出 RAG 个性化学习卡 |
| `POST /feedback` | 输入学习反馈，输出反馈前后变化 |

## 请求示例

```json
{
  "student": {
    "student_id": "stu_001",
    "goals": ["提高 Python 基础"],
    "preferred_styles": ["example", "quiz"],
    "diagnostics": {
      "变量": 0.9,
      "循环": 0.45,
      "函数": 0.35
    }
  },
  "top_k": 5
}
```

## 后续接入

1. 后端把题目作答、点击、停留时长、完成率和反馈写成 `InteractionEvent`。
2. 资源库按 `LearningResource` 字段导出给推荐服务。
3. 接入真实大模型时实现 `LLMClient.generate()`，上层接口无需变化。
4. 有真实日志后，可将规则排序升级为 Learning-to-Rank、LightGBM 或双塔召回模型。

完整设计见 `ml/docs/ml_design.md`。
