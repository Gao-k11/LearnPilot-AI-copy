from __future__ import annotations

from typing import Protocol

from .models import LearningStep, StudentProfile


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class TemplateLLMClient:
    def generate(self, prompt: str) -> str:
        return prompt


class ContentGenerator:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or TemplateLLMClient()

    def generate_study_card(
        self,
        profile: StudentProfile,
        step: LearningStep,
        contexts: list[dict] | None = None,
    ) -> dict[str, str | list[dict]]:
        resources = "、".join(rec.resource.title for rec in step.resources) or "暂无匹配资源"
        contexts = contexts or []
        evidence = "；".join(item["snippet"] for item in contexts) or "使用系统内置课程资源。"
        prompt = (
            f"学生 {profile.student_id} 正在学习 {step.knowledge_point}。"
            f"风险等级：{profile.risk_level}。推荐资源：{resources}。检索依据：{evidence}"
        )
        self.llm_client.generate(prompt)
        return {
            "title": f"{step.knowledge_point} 个性化学习卡",
            "explanation": self._explanation(step.knowledge_point, profile.risk_level),
            "example": self._example(step.knowledge_point, profile.risk_level),
            "practice": self._practice(step.knowledge_point, profile.risk_level),
            "mistake_analysis": f"如果在 {step.knowledge_point} 出错，优先检查概念边界、步骤遗漏和是否套用了不适用的例子。",
            "review_tip": f"完成资源后用 3 句话复述 {step.knowledge_point} 的核心概念，并做一次错因标注。",
            "rag_context": contexts,
        }

    def _explanation(self, point: str, risk_level: str) -> str:
        if risk_level == "high":
            return f"先从生活例子理解 {point}，再看定义，最后做一道低难度题确认是否真的会用。"
        if risk_level == "medium":
            return f"围绕 {point} 梳理概念、适用场景和常见误区，并配合例题巩固。"
        return f"用迁移任务检验 {point}：尝试把它应用到一个新的小项目中。"

    def _practice(self, point: str, risk_level: str) -> str:
        level = "基础" if risk_level == "high" else "进阶" if risk_level == "medium" else "挑战"
        return f"{level}练习：设计并完成 1 道关于 {point} 的题目，提交答案、步骤和自评。"

    def _example(self, point: str, risk_level: str) -> str:
        if risk_level == "high":
            return f"例子：把 {point} 拆成“看输入、做判断、写步骤”三步，每步只处理一个小问题。"
        if risk_level == "medium":
            return f"例子：比较两个相近任务中 {point} 的用法差异，说明什么时候该使用它。"
        return f"例子：在一个小项目里设计 {point} 的变体，并解释你的设计取舍。"
