from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_service import InteractionEvent, LearningMLPipeline
from ml_service.api import app
from ml_service.content_generator import ContentGenerator
from ml_service.data import DEFAULT_RESOURCES
from ml_service.profiler import StudentProfiler
from ml_service.rag import ResourceRetriever

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None


class StudentProfilerTest(unittest.TestCase):
    def test_build_profile_updates_mastery_from_events(self) -> None:
        profiler = StudentProfiler()
        profile = profiler.build_profile(
            "stu",
            {"循环": 0.2},
            [
                InteractionEvent(
                    student_id="stu",
                    resource_id="r1",
                    knowledge_points=("循环",),
                    score=0.8,
                    completed=True,
                    dwell_seconds=600,
                    liked=True,
                )
            ],
        )

        self.assertGreater(profile.mastery["循环"], 0.2)
        self.assertIn(profile.risk_level, {"low", "medium", "high"})
        self.assertIn("循环", profile.recent_focus)
        self.assertGreater(profile.engagement_score, 0.5)
        self.assertGreaterEqual(profile.forgetting_risk, 0.0)


class PipelineTest(unittest.TestCase):
    def test_pipeline_returns_recommendations_path_and_cards(self) -> None:
        pipeline = LearningMLPipeline()
        result = pipeline.recommend(
            student_id="stu_001",
            diagnostics={"变量": 0.85, "条件判断": 0.55, "循环": 0.3, "函数": 0.25},
            preferred_styles=["quiz", "example"],
            top_k=3,
        )

        self.assertEqual(len(result["recommendations"]), 3)
        self.assertGreater(len(result["learning_path"]), 0)
        self.assertGreater(len(result["generated_cards"]), 0)
        self.assertEqual(len(result["agent_traces"]), 5)
        self.assertIn("knowledge_graph", result)
        self.assertEqual(result["profile"]["student_id"], "stu_001")
        self.assertIn("weak_points", result["profile"])
        self.assertIn("forgetting_risk", result["profile"])

    def test_generated_cards_include_rag_context_and_quality_check(self) -> None:
        pipeline = LearningMLPipeline()
        result = pipeline.recommend(
            student_id="stu_002",
            diagnostics={"变量": 0.3, "条件判断": 0.2, "循环": 0.2},
            preferred_styles=["video"],
            top_k=3,
        )

        card = result["generated_cards"][0]
        self.assertIn("rag_context", card)
        self.assertIn("quality_check", card)
        self.assertTrue(card["quality_check"]["passed"])
        self.assertTrue(card["quality_check"]["checks"]["has_rag_evidence"])
        self.assertIn("generation_meta", card)

    def test_feedback_loop_updates_mastery(self) -> None:
        pipeline = LearningMLPipeline()
        result = pipeline.feedback_loop(
            student_id="stu_003",
            diagnostics={"变量": 0.8, "条件判断": 0.5, "循环": 0.25},
            feedback_events=[
                InteractionEvent(
                    student_id="stu_003",
                    resource_id="r003",
                    knowledge_points=("循环",),
                    score=0.9,
                    completed=True,
                    dwell_seconds=800,
                    liked=True,
                )
            ],
            preferred_styles=["quiz"],
            top_k=3,
        )

        self.assertGreater(result["delta"]["循环"], 0)
        self.assertIn("after", result)
        self.assertIn("path_adjustment", result)

    def test_no_matching_resource_still_returns_generated_card(self) -> None:
        pipeline = LearningMLPipeline(resources=[])
        result = pipeline.recommend(
            student_id="stu_004",
            diagnostics={"不存在知识点": 0.2},
            top_k=3,
        )

        self.assertEqual(result["recommendations"], [])
        self.assertGreater(len(result["generated_cards"]), 0)

    def test_previous_mastery_is_merged_into_profile(self) -> None:
        pipeline = LearningMLPipeline()
        result = pipeline.recommend(
            student_id="stu_005",
            diagnostics={"循环": 0.2},
            previous_mastery={"循环": 0.8, "函数": 0.4},
            top_k=3,
        )

        self.assertGreater(result["profile"]["mastery"]["循环"], 0.2)
        self.assertIn("函数", result["profile"]["mastery"])


class RagAndGenerationTest(unittest.TestCase):
    def test_retriever_uses_resource_content(self) -> None:
        retriever = ResourceRetriever()
        contexts = retriever.retrieve("文件读写", DEFAULT_RESOURCES, top_k=3)

        self.assertGreater(len(contexts), 0)
        self.assertEqual(contexts[0]["resource_id"], "r014")
        self.assertIn("snippet", contexts[0])

    def test_generator_falls_back_without_qwen_key(self) -> None:
        class BrokenClient:
            def generate(self, prompt: str) -> str:
                raise RuntimeError("network unavailable")

        pipeline = LearningMLPipeline()
        result = pipeline.recommend(
            student_id="stu_006",
            diagnostics={"变量": 0.3, "条件判断": 0.2},
            top_k=3,
        )
        step = pipeline.planning_agent.plan(
            pipeline.profile_agent.update("stu_006", {"变量": 0.3}, None, None, None)[0],
            pipeline.knowledge_graph,
            pipeline.resources,
        )[0][0]
        card = ContentGenerator(BrokenClient()).generate_study_card(
            pipeline.profile_agent.update("stu_006", {"变量": 0.3}, None, None, None)[0],
            step,
            result["generated_cards"][0]["rag_context"],
        )

        self.assertEqual(card["generation_meta"]["provider"], "template")
        self.assertIn("fallback_reason", card["generation_meta"])


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ApiTest(unittest.TestCase):
    def test_recommend_endpoint_validates_and_returns_profile(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/recommend",
            json={
                "student": {
                    "student_id": "stu_api",
                    "diagnostics": {"变量": 0.4, "循环": 0.2},
                    "preferred_styles": ["quiz"],
                    "previous_mastery": {"函数": 0.3},
                },
                "top_k": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["recommendations"]), 3)
        self.assertIn("forgetting_risk", payload["profile"])

    def test_recommend_endpoint_rejects_invalid_scores(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/recommend",
            json={
                "student": {
                    "student_id": "stu_bad",
                    "diagnostics": {"变量": 1.5},
                },
                "top_k": 3,
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
