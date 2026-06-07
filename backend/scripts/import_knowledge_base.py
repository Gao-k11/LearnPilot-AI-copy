from __future__ import annotations

import os
import re
from pathlib import Path

import pymysql


ROOT_DIR = Path(__file__).resolve().parents[1]
KB_DIR = ROOT_DIR / "data" / "knowledge_base"
ENV_FILE = ROOT_DIR / ".env"

RESOURCE_META = {
    "ai_cnn.md": {"course": "人工智能", "knowledge_point": "CNN", "type": "lecture"},
    "ai_backpropagation.md": {"course": "人工智能", "knowledge_point": "反向传播", "type": "lecture"},
    "ml_decision_tree.md": {"course": "机器学习", "knowledge_point": "决策树", "type": "code_example"},
    "ml_svm.md": {"course": "机器学习", "knowledge_point": "支持向量机", "type": "lecture"},
    "ml_clustering.md": {"course": "机器学习", "knowledge_point": "聚类算法", "type": "reading"},
}


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def connect():
    load_env()
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DATABASE", "learning_agent"),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def extract_title(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback


def get_course_id(cursor, course_name: str) -> int:
    cursor.execute("SELECT id FROM course WHERE name = %s LIMIT 1", (course_name,))
    row = cursor.fetchone()
    if row:
        return int(row["id"])
    cursor.execute("INSERT INTO course (name, description) VALUES (%s, %s)", (course_name, f"{course_name}课程"))
    return int(cursor.lastrowid)


def get_knowledge_point_id(cursor, course_id: int, point_name: str) -> int:
    cursor.execute(
        "SELECT id FROM knowledge_point WHERE course_id = %s AND name = %s LIMIT 1",
        (course_id, point_name),
    )
    row = cursor.fetchone()
    if row:
        return int(row["id"])
    cursor.execute(
        """
        INSERT INTO knowledge_point (course_id, name, description, difficulty)
        VALUES (%s, %s, %s, %s)
        """,
        (course_id, point_name, f"{point_name}知识点", "medium"),
    )
    return int(cursor.lastrowid)


def build_review_card(title: str, content: str) -> str:
    sections = re.findall(r"^##\s+(.+)$", content, flags=re.MULTILINE)
    section_text = "、".join(sections) if sections else "定义、原理、练习、复习"
    return (
        f"# {title} 复习卡片\n\n"
        f"## 覆盖章节\n\n{section_text}\n\n"
        "## 快速复习任务\n\n"
        "1. 用 3 句话复述知识点定义。\n"
        "2. 画出核心原理流程。\n"
        "3. 独立完成例题并解释关键步骤。\n"
        "4. 根据常见误区检查自己的答案。\n\n"
        "## 来源\n\n由 Markdown 知识库素材自动生成。"
    )


def upsert_resource(cursor, course_id: int, point_id: int, title: str, resource_type: str, content: str) -> str:
    cursor.execute("SELECT id FROM course_resource WHERE title = %s LIMIT 1", (title,))
    row = cursor.fetchone()
    if row:
        cursor.execute(
            """
            UPDATE course_resource
            SET course_id = %s,
                knowledge_point_id = %s,
                resource_type = %s,
                content = %s,
                source = 'markdown_import'
            WHERE id = %s
            """,
            (course_id, point_id, resource_type, content, row["id"]),
        )
        return "updated"

    cursor.execute(
        """
        INSERT INTO course_resource (course_id, knowledge_point_id, title, resource_type, content, source)
        VALUES (%s, %s, %s, %s, %s, 'markdown_import')
        """,
        (course_id, point_id, title, resource_type, content),
    )
    return "inserted"


def import_markdown_files() -> None:
    if not KB_DIR.exists():
        raise FileNotFoundError(f"Knowledge base directory not found: {KB_DIR}")

    files = sorted(KB_DIR.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No markdown files found in: {KB_DIR}")

    inserted = 0
    updated = 0
    with connect() as connection:
        try:
            with connection.cursor() as cursor:
                for file_path in files:
                    content = file_path.read_text(encoding="utf-8")
                    meta = RESOURCE_META.get(file_path.name, {})
                    title = extract_title(content, file_path.stem)
                    course_name = meta.get("course", "人工智能")
                    point_name = meta.get("knowledge_point", title)
                    resource_type = meta.get("type", "reading")

                    course_id = get_course_id(cursor, course_name)
                    point_id = get_knowledge_point_id(cursor, course_id, point_name)

                    actions = [
                        upsert_resource(cursor, course_id, point_id, title, resource_type, content),
                        upsert_resource(
                            cursor,
                            course_id,
                            point_id,
                            f"{title} 复习卡片",
                            "review_card",
                            build_review_card(title, content),
                        ),
                    ]
                    inserted += actions.count("inserted")
                    updated += actions.count("updated")

                cursor.execute("SELECT COUNT(*) AS total FROM course_resource")
                total = int(cursor.fetchone()["total"])
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    print(f"Knowledge base import finished. inserted={inserted}, updated={updated}, course_resource_total={total}")


if __name__ == "__main__":
    import_markdown_files()
