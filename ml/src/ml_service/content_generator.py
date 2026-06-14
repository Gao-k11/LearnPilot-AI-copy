from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib import error, request

from .models import LearningStep, StudentProfile


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class TemplateLLMClient:
    def generate(self, prompt: str) -> str:
        return prompt


def load_dotenv_if_present() -> None:
    """Load local .env files without overriding already exported environment variables."""
    candidates = [
        Path.cwd() / "ml" / ".env",
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            item = line.strip()
            if not item or item.startswith("#") or "=" not in item:
                continue
            key, value = item.split("=", 1)
            key = key.strip().lstrip("\ufeff")
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


@dataclass(frozen=True)
class QwenMaxClient:
    api_key: str | None = None
    model: str = "qwen3.7-plus"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "QwenMaxClient | None":
        load_dotenv_if_present()
        if os.getenv("LEARNPILOT_LLM_MODE", "auto").lower() in {"template", "offline", "disabled"}:
            return None
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            model=os.getenv("QWEN_MODEL", "qwen3.7-plus"),
            base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/"),
            timeout_seconds=int(os.getenv("QWEN_TIMEOUT_SECONDS", "30")),
        )

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("Qwen API key is not configured.")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是个性化学习内容生成 Agent。"
                        "请严格返回 JSON，不要添加 Markdown 代码块。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Qwen request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Qwen request failed: {exc.reason}") from exc

        data = json.loads(raw)
        return data["choices"][0]["message"]["content"]


class ContentGenerator:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or QwenMaxClient.from_env() or TemplateLLMClient()

    def generate_study_card(
        self,
        profile: StudentProfile,
        step: LearningStep,
        contexts: list[dict] | None = None,
    ) -> dict[str, str | list[dict] | dict]:
        contexts = contexts or []
        fallback = self._fallback_card(profile, step, contexts)
        if isinstance(self.llm_client, TemplateLLMClient):
            return fallback

        prompt = self._build_prompt(profile, step, contexts)

        try:
            generated = self.llm_client.generate(prompt)
            parsed = self._parse_generated_card(generated)
        except Exception as exc:  # pragma: no cover - protects offline demos.
            fallback["generation_meta"] = {
                "provider": "template",
                "fallback_reason": str(exc),
            }
            return fallback

        merged = {**fallback, **parsed}
        merged["rag_context"] = contexts
        merged["generation_meta"] = {
            "provider": self.llm_client.model if isinstance(self.llm_client, QwenMaxClient) else "custom",
            "fallback_used": False,
        }
        return merged

    def _build_prompt(self, profile: StudentProfile, step: LearningStep, contexts: list[dict]) -> str:
        resources = "、".join(rec.resource.title for rec in step.resources) or "暂无匹配资源"
        evidence = "\n".join(
            f"- {item['title']}：{item['snippet']}" for item in contexts
        ) or "- 使用系统内置课程资源。"
        weak_points = "、".join(profile.weak_points[:5]) or "暂无明显薄弱点"
        goals = "、".join(profile.goals) or "完成当前学习阶段"

        return (
            "请为学生生成一张个性化学习卡，返回 JSON 对象，字段必须包含："
            "title, explanation, example, practice, answer, mistake_analysis, review_tip, evidence_refs, difficulty_reason。"
            f"\n学生ID：{profile.student_id}"
            f"\n学习目标：{goals}"
            f"\n当前知识点：{step.knowledge_point}"
            f"\n目标掌握度：{step.target_mastery}"
            f"\n风险等级：{profile.risk_level}"
            f"\n薄弱点：{weak_points}"
            f"\n学习投入度：{profile.engagement_score}"
            f"\n遗忘风险：{profile.forgetting_risk}"
            f"\n推荐资源：{resources}"
            f"\n检索依据：\n{evidence}"
            "\n要求：内容必须引用检索依据，练习题要可验证，答案要简洁，难度要贴合学生风险等级，避免不可验证建议。"
        )

    def _parse_generated_card(self, generated: str) -> dict[str, str]:
        data = json.loads(generated)
        allowed = {
            "title",
            "explanation",
            "example",
            "practice",
            "answer",
            "mistake_analysis",
            "review_tip",
            "evidence_refs",
            "difficulty_reason",
        }
        return {key: str(value) for key, value in data.items() if key in allowed and value}

    def _fallback_card(
        self,
        profile: StudentProfile,
        step: LearningStep,
        contexts: list[dict],
    ) -> dict[str, str | list[dict] | dict]:
        point = step.knowledge_point
        risk_level = profile.risk_level
        evidence = contexts[0]["title"] if contexts else "系统内置课程资源"
        return {
            "title": f"{point} 个性化学习卡",
            "explanation": self._explanation(point, risk_level, evidence),
            "example": self._example(point, risk_level),
            "practice": self._practice(point, risk_level),
            "answer": f"参考答案应包含 {point} 的关键步骤，并能解释每一步为什么成立。",
            "mistake_analysis": f"如果在 {point} 出错，优先检查概念边界、步骤遗漏和是否套用了不适用的例子。",
            "review_tip": f"完成资源后用 3 句话复述 {point} 的核心概念，并做一次错因标注。",
            "evidence_refs": "；".join(context["chunk_id"] for context in contexts) if contexts else "template",
            "difficulty_reason": f"当前风险等级为 {risk_level}，因此练习难度围绕 {point} 的可验证步骤设计。",
            "rag_context": contexts,
            "generation_meta": {"provider": "template", "fallback_used": True},
        }

    def _explanation(self, point: str, risk_level: str, evidence: str) -> str:
        if risk_level == "high":
            return f"结合《{evidence}》，先从生活例子理解 {point}，再看定义，最后做一道低难度题确认是否真的会用。"
        if risk_level == "medium":
            return f"结合《{evidence}》，围绕 {point} 梳理概念、适用场景和常见误区，并配合例题巩固。"
        return f"结合《{evidence}》，用迁移任务检验 {point}：尝试把它应用到一个新的小项目中。"

    def _practice(self, point: str, risk_level: str) -> str:
        level = "基础" if risk_level == "high" else "进阶" if risk_level == "medium" else "挑战"
        return f"{level}练习：设计并完成 1 道关于 {point} 的题目，提交答案、步骤和自评。"

    def _example(self, point: str, risk_level: str) -> str:
        if risk_level == "high":
            return f"例子：把 {point} 拆成“看输入、做判断、写步骤”三步，每步只处理一个小问题。"
        if risk_level == "medium":
            return f"例子：比较两个相近任务中 {point} 的用法差异，说明什么时候该使用它。"
        return f"例子：在一个小项目里设计 {point} 的变体，并解释你的设计取舍。"
