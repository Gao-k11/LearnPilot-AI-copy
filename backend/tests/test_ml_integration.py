from __future__ import annotations

import sys
import unittest
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_MODE", "sqlite")
os.environ.setdefault("SQLITE_DATABASE_URL", "sqlite://")
os.environ.setdefault("USE_ML_SERVICE", "false")

from backend.app.adapters.ml_adapter import MLAdapter
from backend.app.core.database import Base
from backend.app.models import Course, CourseResource, KnowledgePoint, User
from backend.app.services.learning_service import LearningService


class FakeMLClient:
    def __init__(self, result: dict | None = None, fail: bool = False) -> None:
        self.result = result or {}
        self.fail = fail
        self.payloads: list[dict] = []

    def recommend(self, payload: dict) -> dict:
        self.payloads.append(payload)
        if self.fail:
            raise RuntimeError("ml unavailable")
        return self.result


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def seed_course(db) -> None:
    db.add(User(id=1, username="demo", display_name="Demo", role="student"))
    db.add(Course(id=1, name="人工智能", description="AI course"))
    db.add(KnowledgePoint(id=1, course_id=1, name="CNN", description="Conv nets", difficulty="hard"))
    db.add(KnowledgePoint(id=2, course_id=1, name="反向传播", description="Backprop", difficulty="hard", parent_id=1))
    db.add(
        CourseResource(
            id=1,
            course_id=1,
            knowledge_point_id=1,
            title="CNN 后端课程讲义",
            resource_type="lecture",
            content="卷积、池化、特征图和 CNN 分类流程。",
            source="test",
        )
    )
    db.commit()


class BackendMLIntegrationTest(unittest.TestCase):
    def test_start_learning_sends_backend_course_data_to_ml_and_persists_result(self) -> None:
        db = make_session()
        self.addCleanup(lambda: (db.close(), db.get_bind().dispose()))
        seed_course(db)
        fake_client = FakeMLClient(
            {
                "profile": {
                    "student_id": "1",
                    "mastery": {"CNN": 0.3},
                    "goals": ["学会 CNN"],
                    "preferred_styles": ["video"],
                    "weak_points": ["CNN"],
                    "learning_stage": "foundation",
                },
                "generated_cards": [
                    {
                        "title": "CNN 个性化学习卡",
                        "explanation": "结合后端课程资源讲解 CNN。",
                        "practice": "完成一道卷积输出尺寸计算题。",
                        "answer": "写出计算过程。",
                    }
                ],
                "learning_path": [
                    {
                        "title": "补齐 CNN 基础",
                        "objective": "理解卷积、池化和特征图",
                        "estimated_minutes": 30,
                    }
                ],
            }
        )
        service = LearningService()
        service.ml_adapter = MLAdapter(fake_client)

        profile, resources, path, nodes = service.start_learning(db, 1, 1, "我 CNN 比较薄弱，想准备考试")

        self.assertEqual(fake_client.payloads[0]["resources"][0]["title"], "CNN 后端课程讲义")
        self.assertEqual(fake_client.payloads[0]["resources"][0]["resource_id"], "course_resource:1")
        self.assertEqual(fake_client.payloads[0]["knowledge_graph"][0]["name"], "CNN")
        self.assertIn("CNN", fake_client.payloads[0]["student"]["diagnostics"])
        self.assertIn("CNN", profile["weak_points"])
        self.assertEqual(resources[0].title, "CNN 个性化学习卡")
        self.assertEqual(path.course_id, 1)
        self.assertEqual(nodes[0].title, "补齐 CNN 基础")

    def test_start_learning_falls_back_when_ml_is_unavailable(self) -> None:
        db = make_session()
        self.addCleanup(lambda: (db.close(), db.get_bind().dispose()))
        seed_course(db)
        service = LearningService()
        service.ml_adapter = MLAdapter(FakeMLClient(fail=True))

        profile, resources, path, nodes = service.start_learning(db, 1, 1, "我 CNN 比较薄弱，想准备考试")

        self.assertGreater(len(profile["weak_points"]), 0)
        self.assertGreater(len(resources), 0)
        self.assertEqual(path.course_id, 1)
        self.assertGreater(len(nodes), 0)

    def test_start_learning_keeps_partial_ml_result_and_fills_missing_path(self) -> None:
        db = make_session()
        self.addCleanup(lambda: (db.close(), db.get_bind().dispose()))
        seed_course(db)
        fake_client = FakeMLClient(
            {
                "profile": {
                    "student_id": "1",
                    "weak_points": ["CNN"],
                    "goals": ["学会 CNN"],
                    "preferred_styles": ["video"],
                },
                "generated_cards": [
                    {
                        "title": "只返回资源的 ML 卡片",
                        "explanation": "ML 给出了资源，但没有给路径。",
                        "practice": "补一道 CNN 练习。",
                    }
                ],
            }
        )
        service = LearningService()
        service.ml_adapter = MLAdapter(fake_client)

        profile, resources, path, nodes = service.start_learning(db, 1, 1, "我 CNN 比较薄弱")

        self.assertIn("CNN", profile["weak_points"])
        self.assertEqual(resources[0].title, "只返回资源的 ML 卡片")
        self.assertEqual(path.course_id, 1)
        self.assertGreater(len(nodes), 0)


if __name__ == "__main__":
    unittest.main()
