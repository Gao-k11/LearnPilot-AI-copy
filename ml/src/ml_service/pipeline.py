from __future__ import annotations

from .agents import (
    DiagnosisAgent,
    GenerationEvaluationAgent,
    PlanningAgent,
    ProfileAgent,
    RecommendationAgent,
)
from .data import DEFAULT_KNOWLEDGE_GRAPH, DEFAULT_RESOURCES
from .models import InteractionEvent, KnowledgeNode, LearningResource


class LearningMLPipeline:
    def __init__(
        self,
        resources: list[LearningResource] | None = None,
        knowledge_graph: list[KnowledgeNode] | None = None,
    ) -> None:
        self.resources = DEFAULT_RESOURCES if resources is None else resources
        self.knowledge_graph = DEFAULT_KNOWLEDGE_GRAPH if knowledge_graph is None else knowledge_graph
        self.diagnosis_agent = DiagnosisAgent()
        self.profile_agent = ProfileAgent()
        self.recommendation_agent = RecommendationAgent()
        self.planning_agent = PlanningAgent()
        self.generation_agent = GenerationEvaluationAgent()

    def run_learning_loop(
        self,
        student_id: str,
        diagnostics: dict[str, float],
        events: list[InteractionEvent] | None = None,
        goals: list[str] | None = None,
        preferred_styles: list[str] | None = None,
        previous_mastery: dict[str, float] | None = None,
        top_k: int = 6,
    ) -> dict:
        normalized_diagnostics, diagnosis_trace = self.diagnosis_agent.analyze(diagnostics)
        profile, profile_trace = self.profile_agent.update(
            student_id=student_id,
            diagnostics=normalized_diagnostics,
            events=events,
            goals=goals,
            preferred_styles=preferred_styles,
            previous_mastery=previous_mastery,
        )
        recommendations, recommendation_trace = self.recommendation_agent.recommend(profile, self.resources, top_k=top_k)
        path, planning_trace = self.planning_agent.plan(profile, self.knowledge_graph, self.resources)
        cards, generation_trace = self.generation_agent.generate_cards(profile, path, self.resources)

        return {
            "profile": {
                "student_id": profile.student_id,
                "mastery": profile.mastery,
                "goals": profile.goals,
                "preferred_styles": profile.preferred_styles,
                "target_difficulty": profile.target_difficulty,
                "risk_level": profile.risk_level,
                "weak_points": profile.weak_points,
                "recent_focus": profile.recent_focus,
                "learning_velocity": profile.learning_velocity,
                "engagement_score": profile.engagement_score,
                "stability_score": profile.stability_score,
                "preference_confidence": profile.preference_confidence,
                "forgetting_risk": profile.forgetting_risk,
            },
            "recommendations": [
                {
                    "resource_id": item.resource.resource_id,
                    "title": item.resource.title,
                    "score": item.score,
                    "style": item.resource.style,
                    "difficulty": item.resource.difficulty,
                    "reasons": list(item.reasons),
                }
                for item in recommendations
            ],
            "learning_path": [
                {
                    "knowledge_point": step.knowledge_point,
                    "target_mastery": step.target_mastery,
                    "rationale": step.rationale,
                    "resources": [rec.resource.title for rec in step.resources],
                }
                for step in path
            ],
            "generated_cards": cards,
            "knowledge_graph": [
                {
                    "name": node.name,
                    "prerequisites": list(node.prerequisites),
                    "importance": node.importance,
                    "mastery": profile.mastery.get(node.name, 0.5),
                }
                for node in self.knowledge_graph
            ],
            "agent_traces": [
                diagnosis_trace.__dict__,
                profile_trace.__dict__,
                recommendation_trace.__dict__,
                planning_trace.__dict__,
                generation_trace.__dict__,
            ],
        }

    def recommend(self, *args, **kwargs) -> dict:
        return self.run_learning_loop(*args, **kwargs)

    def diagnose(self, answers: dict[str, float]) -> dict:
        diagnostics, trace = self.diagnosis_agent.analyze(answers)
        return {"diagnostics": diagnostics, "agent_trace": trace.__dict__}

    def feedback_loop(
        self,
        student_id: str,
        diagnostics: dict[str, float],
        feedback_events: list[InteractionEvent],
        goals: list[str] | None = None,
        preferred_styles: list[str] | None = None,
        previous_mastery: dict[str, float] | None = None,
        top_k: int = 6,
    ) -> dict:
        before = self.run_learning_loop(
            student_id,
            diagnostics,
            goals=goals,
            preferred_styles=preferred_styles,
            previous_mastery=previous_mastery,
            top_k=top_k,
        )
        after = self.run_learning_loop(
            student_id,
            diagnostics,
            events=feedback_events,
            goals=goals,
            preferred_styles=preferred_styles,
            previous_mastery=before["profile"]["mastery"],
            top_k=top_k,
        )
        return {
            "before": before,
            "after": after,
            "delta": {
                point: round(after["profile"]["mastery"].get(point, 0.0) - before["profile"]["mastery"].get(point, 0.0), 4)
                for point in set(before["profile"]["mastery"]) | set(after["profile"]["mastery"])
            },
            "path_adjustment": self._path_adjustment(before, after),
        }

    def _path_adjustment(self, before: dict, after: dict) -> str:
        before_path = [step["knowledge_point"] for step in before["learning_path"]]
        after_path = [step["knowledge_point"] for step in after["learning_path"]]
        if before_path == after_path:
            return "学习路径保持稳定，系统将根据掌握度变化微调资源难度。"
        return f"路径从 {' → '.join(before_path[:4])} 调整为 {' → '.join(after_path[:4])}。"
