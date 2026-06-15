from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_MODE", "sqlite")
os.environ.setdefault("SQLITE_DATABASE_URL", "sqlite://")
os.environ.setdefault("USE_ML_SERVICE", "false")
os.environ.setdefault("LEARNPILOT_LLM_MODE", "template")

from fastapi.testclient import TestClient

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models import Course, KnowledgePoint


class ProductionApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        with self.Session() as db:
            db.add(Course(id=1, name="人工智能", description="AI"))
            db.add(KnowledgePoint(id=1, course_id=1, name="CNN", description="Conv", difficulty="hard"))
            db.commit()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_auth_import_and_question_flow(self) -> None:
        teacher = self.client.post(
            "/api/v1/auth/register",
            json={"username": "teacher1", "password": "secret123", "role": "teacher"},
        )
        self.assertEqual(teacher.status_code, 200)
        token = teacher.json()["access_token"]

        imported = self.client.post(
            "/api/v1/courses/1/resources/import",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "filename": "cnn.md",
                "source_type": "markdown",
                "content": "# CNN 入门\nCNN 包含卷积、池化和特征图。",
            },
        )
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["status"], "completed")

        resources = self.client.get("/api/v1/courses/1/resources")
        self.assertEqual(resources.status_code, 200)
        self.assertEqual(resources.json()[0]["title"], "CNN 入门")

        questions = self.client.post(
            "/api/v1/courses/1/resources/import",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "filename": "questions.json",
                "source_type": "question_json",
                "content": '{"questions":[{"stem":"CNN 中池化有什么作用？","answer":"降采样","difficulty":0.4}]}',
            },
        )
        self.assertEqual(questions.status_code, 200)
        listed = self.client.get("/api/v1/courses/1/questions")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["stem"], "CNN 中池化有什么作用？")

    def test_student_cannot_import_resources(self) -> None:
        student = self.client.post(
            "/api/v1/auth/register",
            json={"username": "student1", "password": "secret123", "role": "student"},
        )
        token = student.json()["access_token"]
        response = self.client.post(
            "/api/v1/courses/1/resources/import",
            headers={"Authorization": f"Bearer {token}"},
            json={"filename": "x.md", "source_type": "markdown", "content": "# x"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
