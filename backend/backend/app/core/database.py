from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine_kwargs = {"pool_pre_ping": True}
if settings.is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_recycle"] = 3600

engine = create_engine(
    settings.database_url,
    **engine_kwargs,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def ensure_user_columns() -> None:
    inspector = inspect(engine)
    if "user" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("user")}
    dialect = engine.dialect.name
    quote = "`" if dialect == "mysql" else '"'
    table_name = f"{quote}user{quote}"
    timestamp_type = "DATETIME" if dialect == "mysql" else "TIMESTAMP"
    columns = {
        "email": "VARCHAR(255) NULL",
        "is_admin": "BOOLEAN NULL DEFAULT false",
        "status": "VARCHAR(32) NULL DEFAULT 'active'",
        "created_at": f"{timestamp_type} NULL",
        "updated_at": f"{timestamp_type} NULL",
    }

    with engine.begin() as connection:
        for column_name, column_type in columns.items():
            if column_name not in column_names:
                quoted_column = f"{quote}{column_name}{quote}"
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {quoted_column} {column_type}")
                )
        if dialect in {"mysql", "postgresql"}:
            username_indexes = {
                index["name"]
                for index in inspector.get_indexes("user")
                if index.get("unique") and index.get("column_names") == ["username"]
            }
            username_constraints = {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("user")
                if constraint.get("name") and constraint.get("column_names") == ["username"]
            }

            for constraint_name in username_constraints:
                quoted_constraint = f"{quote}{constraint_name}{quote}"
                if dialect == "mysql":
                    connection.execute(text(f"ALTER TABLE {table_name} DROP INDEX {quoted_constraint}"))
                else:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {quoted_constraint}")
                    )

            for index_name in username_indexes - username_constraints:
                quoted_index = f"{quote}{index_name}{quote}"
                if dialect == "mysql":
                    connection.execute(text(f"ALTER TABLE {table_name} DROP INDEX {quoted_index}"))
                else:
                    connection.execute(text(f"DROP INDEX IF EXISTS {quoted_index}"))


def ensure_student_profile_columns() -> None:
    inspector = inspect(engine)
    if "student_profile" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("student_profile")}
    dialect = engine.dialect.name
    table_name = "`student_profile`" if dialect == "mysql" else '"student_profile"'
    columns = {
        "mastery": "TEXT NULL",
        "weak_points_json": "TEXT NULL",
        "engagement_score": "FLOAT NULL",
        "forgetting_risk": "FLOAT NULL",
        "learning_stage": "VARCHAR(64) NULL",
    }

    with engine.begin() as connection:
        for column_name, column_type in columns.items():
            if column_name not in column_names:
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                )


def ensure_course_resource_columns() -> None:
    inspector = inspect(engine)
    if "course_resource" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("course_resource")}
    dialect = engine.dialect.name
    quote = "`" if dialect == "mysql" else '"'
    table_name = f"{quote}course_resource{quote}"
    columns = {
        "source_type": "VARCHAR(64) NULL",
        "status": "VARCHAR(32) NULL DEFAULT 'published'",
        "version": "VARCHAR(32) NULL DEFAULT 'v1'",
        "metadata": "TEXT NULL",
    }

    with engine.begin() as connection:
        for column_name, column_type in columns.items():
            if column_name not in column_names:
                quoted_column = f"{quote}{column_name}{quote}"
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {quoted_column} {column_type}")
                )


def ensure_resource_center_columns() -> None:
    inspector = inspect(engine)
    if "resource_center" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("resource_center")}
    dialect = engine.dialect.name
    quote = "`" if dialect == "mysql" else '"'
    table_name = f"{quote}resource_center{quote}"
    columns = {
        "open_type": "VARCHAR(32) NULL DEFAULT 'content'",
        "knowledge_point": "VARCHAR(128) NULL",
        "tags": "VARCHAR(255) NULL",
        "difficulty": "VARCHAR(32) NULL",
        "summary": "TEXT NULL",
    }

    with engine.begin() as connection:
        for column_name, column_type in columns.items():
            if column_name not in column_names:
                quoted_column = f"{quote}{column_name}{quote}"
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {quoted_column} {column_type}")
                )


def ensure_producer_columns() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    dialect = engine.dialect.name
    quote = "`" if dialect == "mysql" else '"'
    table_columns = {
        "producer_task": {
            "task_id": "VARCHAR(64) NULL",
            "user_id": "INTEGER NULL",
            "topic": "VARCHAR(255) NULL",
            "requirement": "TEXT NULL",
            "task_type": "VARCHAR(64) NULL",
            "status": "VARCHAR(32) NULL DEFAULT 'pending'",
            "progress": "INTEGER NULL DEFAULT 0",
            "result_json": "TEXT NULL",
            "error_message": "TEXT NULL",
            "created_at": "TIMESTAMP NULL",
            "updated_at": "TIMESTAMP NULL",
        },
        "producer_artifact": {
            "task_id": "VARCHAR(64) NULL",
            "artifact_type": "VARCHAR(64) NULL",
            "title": "VARCHAR(255) NULL",
            "content": "TEXT NULL",
            "url": "VARCHAR(512) NULL",
            "metadata_json": "TEXT NULL",
            "created_at": "TIMESTAMP NULL",
            "updated_at": "TIMESTAMP NULL",
        },
        "producer_chat_message": {
            "session_id": "VARCHAR(64) NULL",
            "role": "VARCHAR(32) NULL",
            "content": "TEXT NULL",
            "created_at": "TIMESTAMP NULL",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in table_columns.items():
            if table_name not in table_names:
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            quoted_table = f"{quote}{table_name}{quote}"
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    quoted_column = f"{quote}{column_name}{quote}"
                    connection.execute(
                        text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {column_type}")
                    )


def ensure_learning_path_columns() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    dialect = engine.dialect.name
    quote = "`" if dialect == "mysql" else '"'
    table_columns = {
        "learning_path": {
            "progress": "FLOAT NULL DEFAULT 0",
        },
        "learning_path_node": {
            "description": "TEXT NULL",
            "level": "VARCHAR(64) NULL",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in table_columns.items():
            if table_name not in table_names:
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            quoted_table = f"{quote}{table_name}{quote}"
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    quoted_column = f"{quote}{column_name}{quote}"
                    connection.execute(
                        text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {column_type}")
                    )


def ensure_ml_profile_answer_columns() -> None:
    inspector = inspect(engine)
    if "ml_profile_answer" not in inspector.get_table_names():
        return

    dialect = engine.dialect.name
    quote = "`" if dialect == "mysql" else '"'
    table_name = f"{quote}ml_profile_answer{quote}"
    existing = {column["name"] for column in inspector.get_columns("ml_profile_answer")}
    columns = {
        "user_id": "INTEGER NULL",
        "session_id": "VARCHAR(64) NULL",
        "question_id": "VARCHAR(128) NULL",
        "question": "TEXT NULL",
        "answer": "TEXT NULL",
        "created_at": "TIMESTAMP NULL",
    }
    with engine.begin() as connection:
        for column_name, column_type in columns.items():
            if column_name not in existing:
                quoted_column = f"{quote}{column_name}{quote}"
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {quoted_column} {column_type}")
                )
