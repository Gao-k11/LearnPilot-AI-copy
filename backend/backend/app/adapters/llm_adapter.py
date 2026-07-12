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

    def tutor_answer(
        self,
        question: str,
        profile: dict | None = None,
        history: list[str] | None = None,
        evidence: list[dict] | None = None,
    ) -> dict:
        prompt = self._build_tutor_prompt(question, profile, history, evidence)
        generated = self._qwen_json(prompt)
        if generated:
            return {
                "answer": str(generated.get("answer") or ""),
                "hints": [str(item) for item in (generated.get("hints") or []) if item],
                "next_action": str(generated.get("next_action") or "完成一个小练习并复盘。"),
            }
        return self._tutor_template_fallback(question, profile, history, evidence)

    def _build_tutor_prompt(
        self,
        question: str,
        profile: dict | None,
        history: list[str] | None,
        evidence: list[dict] | None,
    ) -> str:
        profile = profile or {}
        history_lines = list(history or [])[-10:]
        evidence_items = list(evidence or [])[:5]

        profile_block = "\n".join(
            [
                f"- 专业：{profile.get('major') or '未提供'}",
                f"- 年级：{profile.get('grade') or '未提供'}",
                f"- 当前课程：{profile.get('course') or '未提供'}",
                f"- 学习目标：{profile.get('goal') or '未提供'}",
                f"- 薄弱点：{', '.join(profile.get('weak_points') or []) or '未提供'}",
                f"- 学习偏好：{profile.get('preference') or '未提供'}",
                f"- 认知风格：{profile.get('cognitive_style') or '未提供'}",
                f"- 知识水平：{profile.get('knowledge_level') or '未提供'}",
            ]
        )

        history_block = "\n".join(history_lines) if history_lines else "（无）"
        evidence_block = "\n".join(self._format_evidence_line(item) for item in evidence_items) or "（无可靠检索证据）"

        return (
            "你是 LearnPilot-AI 智能辅导老师。请根据学生画像、最近对话和检索证据，用适合学生当前水平的中文回答问题。\n"
            "要求：\n"
            "1. 先直接回答问题，再给例子或简要推导。\n"
            "2. 回答可使用 Markdown（标题、列表、代码块）。\n"
            "3. 不要编造不存在的引用；没有可靠证据时明确说明。\n"
            "4. 不要输出 JWT、密码、邮箱等敏感信息。\n"
            "5. 严格返回 JSON，字段：answer（完整讲解，Markdown 字符串）、hints（字符串数组）、next_action（字符串）。\n\n"
            f"学生问题：{question}\n\n"
            f"学生画像：\n{profile_block}\n\n"
            f"最近对话：\n{history_block}\n\n"
            f"检索证据（仅可引用以下内容，无则不要虚构）：\n{evidence_block}"
        )

    def _format_evidence_line(self, item: dict) -> str:
        title = str(item.get("title") or f"资源 {item.get('resource_id') or '未知'}")
        source = str(item.get("source") or item.get("resource_id") or item.get("chunk_id") or "未知来源")
        snippet = str(item.get("snippet") or item.get("summary") or "")[:240]
        return f"- 标题：{title}；来源：{source}；摘要：{snippet}"

    def _tutor_template_fallback(
        self,
        question: str,
        profile: dict | None,
        history: list[str] | None,
        evidence: list[dict] | None,
    ) -> dict:
        profile = profile or {}
        course = profile.get("course") or "当前课程"
        level = profile.get("knowledge_level") or "当前水平"
        weak_points = profile.get("weak_points") or []
        weak_text = "、".join(str(item) for item in weak_points[:3]) if weak_points else "基础概念"

        evidence_items = list(evidence or [])[:5]
        evidence_lines = [self._format_evidence_line(item) for item in evidence_items]
        evidence_section = "\n".join(evidence_lines) if evidence_lines else "暂无可靠课程检索证据，以下回答基于通用教学逻辑。"

        history_hint = ""
        if history:
            history_hint = f" 结合你刚才的对话（最近 {min(len(history), 10)} 条），"

        answer = (
            f"## 问题理解\n\n"
            f"你问的是：**{question}**。{history_hint}我会按 **{level}** 水平、结合 **{course}** 来讲解。\n\n"
            f"## 核心回答\n\n"
            f"建议先把问题拆成三部分：涉及的概念、已知条件、期望结论。针对“{question}”，"
            f"可以先回顾与 **{weak_text}** 相关的定义，再用一个最小例子验证自己的理解。\n\n"
            f"## 参考资料\n\n{evidence_section}"
        )

        return {
            "answer": answer,
            "hints": [
                "先用自己的话复述题目",
                "标出已知条件与待求目标",
                "用一个最小数值或代码例子验证",
            ],
            "next_action": f"围绕“{question}”完成一个 5 分钟小练习，并写下推理过程。",
        }
