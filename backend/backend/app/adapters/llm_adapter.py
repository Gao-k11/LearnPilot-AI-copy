from __future__ import annotations

import json
from urllib import error, request

from backend.app.core.config import get_settings


class MockLLMAdapter:
    """DashScope Qwen adapter with deterministic template fallback for demo/offline mode."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def _qwen_json(self, prompt: str) -> dict | None:
        if self.settings.learnpilot_llm_mode.lower() in {"template", "offline", "disabled"}:
            return None
        if not self.settings.dashscope_api_key:
            return None
        payload = {
            "model": "qwen3.7-plus",
            "messages": [
                {"role": "system", "content": "你是 LearnPilot-AI 教学智能体，请严格返回 JSON。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.35,
            "response_format": {"type": "json_object"},
        }
        req = request.Request(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.settings.dashscope_api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                raw = json.loads(response.read().decode("utf-8"))
            return json.loads(raw["choices"][0]["message"]["content"])
        except (error.HTTPError, error.URLError, KeyError, json.JSONDecodeError, TimeoutError):
            return None

    def profile_from_text(self, text: str) -> dict:
        generated = self._qwen_json(
            "请从学生学习需求中抽取画像，返回字段：major, grade, course, goal, weak_points, "
            f"preference, cognitive_style, knowledge_level。学习需求：{text}"
        )
        if generated:
            generated.setdefault("weak_points", [])
            return generated
        weak_points = []
        for keyword in ["CNN", "卷积神经网络", "反向传播", "注意力机制", "Transformer", "机器学习"]:
            if keyword.lower() in text.lower():
                weak_points.append(keyword)
        if not weak_points:
            weak_points = ["基础概念", "知识迁移"]

        course = "人工智能"
        if "软件工程" in text:
            major = "软件工程"
        else:
            major = "未明确"

        return {
            "major": major,
            "grade": "大二" if "大二" in text else "未明确",
            "course": course,
            "goal": "准备考试" if "考试" in text else "提升课程掌握度",
            "weak_points": weak_points,
            "preference": "结构化讲义 + 练习题",
            "cognitive_style": "循序渐进型",
            "knowledge_level": "入门到中级",
        }

    def generate_resource(self, topic: str, resource_type: str, weak_points: list[str]) -> str:
        generated = self._qwen_json(
            "请生成教学资源，返回 JSON 字段 content，要求可验证、分层讲解并避免幻觉。"
            f"主题：{topic}；资源类型：{resource_type}；薄弱点：{weak_points}"
        )
        if generated and generated.get("content"):
            return str(generated["content"])
        weak_text = "、".join(weak_points) if weak_points else topic
        templates = {
            "lecture": f"讲义：围绕 {topic} 建立概念、公式/流程、常见误区和例题。重点补齐：{weak_text}。",
            "mind_map": f"思维导图：{topic} -> 核心概念 -> 关键步骤 -> 典型应用 -> 易错点：{weak_text}。",
            "exercise": f"练习题：1. 解释 {topic} 的核心思想。2. 分析 {weak_text} 的应用场景。3. 完成一道综合题并写出推理过程。",
            "reading": f"拓展阅读：推荐阅读课程教材相关章节、经典论文综述和工程案例，阅读时记录 {weak_text} 的问题清单。",
            "code_example": f"代码案例：使用 Python 构建 {topic} 的最小示例，包含数据准备、核心函数、结果解释和调参提示。",
            "video_script": f"视频脚本：开场提出问题，分三段讲解 {topic}，用可视化例子解释 {weak_text}，最后给出复盘任务。",
        }
        return templates.get(resource_type, f"{resource_type}：关于 {topic} 的学习材料。")

    def tutor_answer(self, question: str) -> dict:
        generated = self._qwen_json(
            "请用苏格拉底式引导回答学生问题，返回 JSON 字段 answer, hints, next_action。"
            f"学生问题：{question}"
        )
        if generated:
            return {
                "answer": str(generated.get("answer") or ""),
                "hints": list(generated.get("hints") or []),
                "next_action": str(generated.get("next_action") or "完成一个小练习并复盘。"),
            }
        return {
            "answer": (
                "我们先不直接给结论。你可以先判断这个问题涉及哪个概念、输入是什么、期望输出是什么。"
                f" 针对你的问题“{question}”，建议先画出信息流，再定位卡住的步骤。"
            ),
            "hints": ["先复述题意", "找出已知条件和目标", "用一个最小例子验证理解"],
            "next_action": "完成一个 5 分钟小练习，并把推理过程写下来。",
        }
