from __future__ import annotations

from .models import KnowledgeNode, LearningResource, LearningStep, StudentProfile
from .recommender import ResourceRecommender


class LearningPathPlanner:
    def __init__(self, recommender: ResourceRecommender | None = None) -> None:
        self.recommender = recommender or ResourceRecommender()

    def plan(
        self,
        profile: StudentProfile,
        knowledge_graph: list[KnowledgeNode],
        resources: list[LearningResource],
        max_steps: int = 5,
    ) -> list[LearningStep]:
        ordered_points = self._ordered_targets(profile, knowledge_graph)[:max_steps]
        steps: list[LearningStep] = []

        for point in ordered_points:
            candidates = [resource for resource in resources if point in resource.knowledge_points]
            recommendations = self.recommender.recommend(profile, candidates, top_k=3)
            current = profile.mastery.get(point, 0.5)
            target = min(0.9, max(0.7, current + 0.25))
            steps.append(
                LearningStep(
                    knowledge_point=point,
                    target_mastery=round(target, 2),
                    resources=tuple(recommendations),
                    rationale=f"{self._stage_goal(current)}：当前掌握度 {current:.2f}，优先补齐到 {target:.2f}",
                )
            )

        return steps

    def _ordered_targets(self, profile: StudentProfile, knowledge_graph: list[KnowledgeNode]) -> list[str]:
        nodes = {node.name: node for node in knowledge_graph}
        weak_points = sorted(
            nodes,
            key=lambda point: ((1.0 - profile.mastery.get(point, 0.5)) * nodes[point].importance),
            reverse=True,
        )

        visited: set[str] = set()
        ordered: list[str] = []

        def visit(point: str) -> None:
            if point in visited or point not in nodes:
                return
            for prereq in nodes[point].prerequisites:
                if profile.mastery.get(prereq, 0.0) < 0.7:
                    visit(prereq)
            visited.add(point)
            ordered.append(point)

        for point in weak_points:
            if profile.mastery.get(point, 0.5) < 0.75:
                visit(point)
        return ordered

    def _stage_goal(self, mastery: float) -> str:
        if mastery < 0.45:
            return "补基础"
        if mastery < 0.65:
            return "练专项"
        if mastery < 0.78:
            return "做综合"
        return "项目迁移"
