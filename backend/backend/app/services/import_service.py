from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models import CourseResource, ImportJob, KnowledgePoint, Question, ResourceChunk


class ResourceImportService:
    def import_payload(
        self,
        db: Session,
        course_id: int,
        user_id: int,
        filename: str,
        source_type: str,
        content: str,
    ) -> ImportJob:
        job = ImportJob(
            course_id=course_id,
            user_id=user_id,
            source_type=source_type,
            filename=filename,
            status="running",
            message="import started",
        )
        db.add(job)
        db.flush()
        try:
            if not content.strip():
                raise ValueError("import content is empty")
            if source_type in {"question_json", "mistake_json"}:
                result = self._import_questions(db, course_id, filename, content)
            else:
                result = self._import_document(db, course_id, filename, source_type, content)
            job.status = "completed"
            job.message = "import completed"
            job.result = result
            db.add(job)
            db.commit()
            db.refresh(job)
            return job
        except Exception as exc:
            job.status = "failed"
            job.message = str(exc)
            db.add(job)
            db.commit()
            db.refresh(job)
            return job

    def _import_document(self, db: Session, course_id: int, filename: str, source_type: str, content: str) -> dict:
        title = self._title_from_document(filename, content)
        point = self._match_knowledge_point(db, course_id, content)
        clean = self._clean_text(content)
        resource = CourseResource(
            course_id=course_id,
            knowledge_point_id=point.id if point else None,
            title=title,
            resource_type="reading" if source_type == "markdown" else "lecture",
            content=clean,
            source=filename,
            source_type=source_type,
            status="published",
            version="v1",
            resource_metadata={"content_hash": hashlib.sha256(clean.encode("utf-8")).hexdigest()},
        )
        db.add(resource)
        db.flush()
        chunks = self._write_chunks(db, resource, course_id, clean)
        return {"resources": 1, "chunks": chunks, "matched_knowledge_point": point.name if point else None}

    def _import_questions(self, db: Session, course_id: int, filename: str, content: str) -> dict:
        data = json.loads(content)
        items = data if isinstance(data, list) else data.get("questions", [])
        if not isinstance(items, list):
            raise ValueError("question payload must be a list or contain a questions list")
        count = 0
        for item in items:
            if not isinstance(item, dict) or not item.get("stem"):
                continue
            point = self._match_knowledge_point(db, course_id, " ".join(str(item.get(key, "")) for key in item))
            db.add(
                Question(
                    course_id=course_id,
                    knowledge_point_id=point.id if point else None,
                    question_type=str(item.get("question_type") or item.get("type") or "short_answer"),
                    stem=str(item["stem"]),
                    answer=str(item.get("answer") or ""),
                    explanation=str(item.get("explanation") or ""),
                    difficulty=float(item.get("difficulty") or 0.5),
                    source=filename,
                )
            )
            count += 1
        return {"questions": count}

    def _write_chunks(self, db: Session, resource: CourseResource, course_id: int, content: str) -> int:
        chunks = self._split_text(content)
        for index, chunk in enumerate(chunks, start=1):
            db.add(
                ResourceChunk(
                    resource_id=resource.id,
                    course_id=course_id,
                    chunk_index=index,
                    content=chunk,
                    token_count=len(chunk),
                    keywords=self._keywords(chunk),
                    embedding=self._embedding_stub(chunk),
                )
            )
        return len(chunks)

    def _match_knowledge_point(self, db: Session, course_id: int, text: str) -> KnowledgePoint | None:
        points = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
        lowered = text.lower()
        for point in points:
            if point.name.lower() in lowered:
                return point
        return points[0] if points else None

    def _clean_text(self, content: str) -> str:
        return re.sub(r"\s+", " ", content.replace("\ufeff", " ")).strip()

    def _title_from_document(self, filename: str, content: str) -> str:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip() or filename
        return filename.rsplit(".", 1)[0]

    def _split_text(self, text: str, chunk_size: int = 600, overlap: int = 80) -> list[str]:
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = max(start + 1, end - overlap)
        return chunks

    def _keywords(self, text: str) -> list[str]:
        words = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", text)
        seen: list[str] = []
        for word in words:
            if word not in seen:
                seen.append(word)
            if len(seen) >= 20:
                break
        return seen

    def _embedding_stub(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [round(byte / 255, 6) for byte in digest[:16]]


resource_import_service = ResourceImportService()
