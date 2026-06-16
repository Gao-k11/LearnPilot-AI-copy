from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DATABASE_MODE", "postgres")

from backend.app import models as _models  # noqa: F401
from backend.app.core.database import (
    Base,
    engine,
    ensure_course_resource_columns,
    ensure_learning_path_columns,
    ensure_ml_profile_answer_columns,
    ensure_producer_columns,
    ensure_resource_center_columns,
    ensure_student_profile_columns,
    ensure_user_columns,
)


def init_postgres_schema() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_user_columns()
    ensure_student_profile_columns()
    ensure_course_resource_columns()
    ensure_resource_center_columns()
    ensure_producer_columns()
    ensure_learning_path_columns()
    ensure_ml_profile_answer_columns()
    print("PostgreSQL schema initialized. ML integration columns are compatible.")


if __name__ == "__main__":
    init_postgres_schema()
