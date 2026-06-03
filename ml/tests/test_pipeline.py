from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_service import InteractionEvent, LearningMLPipeline
from ml_service.profiler import StudentProfiler


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


if __name__ == "__main__":
    unittest.main()
