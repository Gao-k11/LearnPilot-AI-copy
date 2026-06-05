from __future__ import annotations

from dataclasses import dataclass

from .content_generator import ContentGenerator
from .models import InteractionEvent, LearningStep, StudentProfile
from .path_planner import LearningPathPlanner
from .profiler import StudentProfiler
from .ranker import TrainableRanker
from .rag import ResourceRetriever
from .recommender import ResourceRecommender


@dataclass(frozen=True)
class AgentTrace:
    agent: str
    action: str
    output: str


class DiagnosisAgent:
    def analyze(self, answers: dict[str, float]) -> tuple[dict[str, float], AgentTrace]:
        diagnostics = {point: max(0.0, min(1.0, float(score))) for point, score in answers.items()}
        weak = [point for point, score in diagnostics.items() if score < 0.6]
        output = "发现薄弱点：" + ("、".join(weak) if weak else "暂无明显薄弱点")
        return diagnostics, AgentTrace("诊断 Agent", "分析测评答案并输出知识点掌握度", output)


class ProfileAgent:
    def __init__(self, profiler: StudentProfiler | None = None) -> None:
        self.profiler = profiler or StudentProfiler()

    def update(
        self,
        student_id: str,
        diagnostics: dict[str, float],
        events: list[InteractionEvent] | None,
        goals: list[str] | None,
        preferred_styles: list[str] | None,
        previous_mastery: dict[str, float] | None = None,
    ) -> tuple[StudentProfile, AgentTrace]:
        profile = self.profiler.build_profile(student_id, diagnostics, events, goals, preferred_styles, previous_mastery)
        weakest = sorted(profile.mastery, key=profile.mastery.get)[:2]
        output = f"风险等级 {profile.risk_level}，优先关注 {'、'.join(weakest) if weakest else '目标知识点'}"
        return profile, AgentTrace("画像 Agent", "融合诊断、行为和偏好，维护学生画像", output)


class RecommendationAgent:
    def __init__(self, recommender: ResourceRecommender | None = None, ranker: TrainableRanker | None = None) -> None:
        self.recommender = recommender or ResourceRecommender()
        self.ranker = ranker or TrainableRanker()

    def recommend(self, profile: StudentProfile, resources, top_k: int):
        recommendations = self.ranker.recommend(profile, resources, top_k=top_k)
        if not recommendations:
            recommendations = self.recommender.recommend(profile, resources, top_k=top_k)
        titles = [item.resource.title for item in recommendations[:3]]
        trace = AgentTrace(
            "推荐 Agent",
            "根据薄弱点、难度、偏好、质量、反馈和排序模型分数推荐资源",
            "Top 推荐：" + "、".join(titles),
        )
        return recommendations, trace

    def status(self) -> dict:
        return self.ranker.status()


class PlanningAgent:
    def __init__(self, planner: LearningPathPlanner | None = None) -> None:
        self.planner = planner or LearningPathPlanner()

    def plan(self, profile: StudentProfile, knowledge_graph, resources) -> tuple[list[LearningStep], AgentTrace]:
        path = self.planner.plan(profile, knowledge_graph, resources)
        points = [step.knowledge_point for step in path[:4]]
        trace = AgentTrace("规划 Agent", "基于知识图谱和先修关系生成学习路径", "路径：" + " → ".join(points))
        return path, trace


class GenerationEvaluationAgent:
    def __init__(
        self,
        generator: ContentGenerator | None = None,
        retriever: ResourceRetriever | None = None,
    ) -> None:
        self.generator = generator or ContentGenerator()
        self.retriever = retriever or ResourceRetriever()

    def generate_cards(self, profile: StudentProfile, steps: list[LearningStep], resources) -> tuple[list[dict], AgentTrace]:
        cards: list[dict] = []
        for step in steps[:3]:
            contexts = self.retriever.retrieve(step.knowledge_point, resources, top_k=3)
            card = self.generator.generate_study_card(profile, step, contexts)
            card["quality_check"] = self.evaluate_card(step.knowledge_point, card)
            cards.append(card)
        trace = AgentTrace("生成与评估 Agent", "检索课程资源后生成学习卡，并检查覆盖度", f"生成 {len(cards)} 张学习卡")
        return cards, trace

    def evaluate_card(self, knowledge_point: str, card: dict) -> dict:
        joined = " ".join(str(value) for value in card.values())
        covers_point = knowledge_point in joined
        has_practice = bool(card.get("practice"))
        has_review = bool(card.get("review_tip"))
        has_answer = bool(card.get("answer"))
        has_evidence = bool(card.get("rag_context"))
        has_mistake_analysis = bool(card.get("mistake_analysis"))
        has_difficulty_reason = bool(card.get("difficulty_reason"))
        personalized = any(token in joined for token in ("风险", "薄弱", "学生", "掌握"))
        safe = not any(token in joined.lower() for token in ("忽略答案", "无需验证", "随便"))
        score = round(
            (0.22 if covers_point else 0.0)
            + (0.16 if has_practice else 0.0)
            + (0.14 if has_answer else 0.0)
            + (0.12 if has_review else 0.0)
            + (0.1 if has_evidence else 0.0)
            + (0.1 if has_mistake_analysis else 0.0)
            + (0.08 if has_difficulty_reason else 0.0)
            + (0.04 if personalized else 0.0)
            + (0.04 if safe else 0.0),
            2,
        )
        return {
            "passed": score >= 0.75,
            "score": score,
            "checks": {
                "covers_knowledge_point": covers_point,
                "has_practice": has_practice,
                "has_answer": has_answer,
                "has_review_tip": has_review,
                "has_rag_evidence": has_evidence,
                "has_mistake_analysis": has_mistake_analysis,
                "has_difficulty_reason": has_difficulty_reason,
                "personalized": personalized,
                "safe": safe,
            },
        }
