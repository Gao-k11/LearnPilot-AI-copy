from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .models import LearningResource


@dataclass(frozen=True)
class ResourceChunk:
    resource: LearningResource
    chunk_id: str
    text: str
    tokens: tuple[str, ...]


class ResourceRetriever:
    """BM25-style retriever over local course resources and resource content."""

    def retrieve(self, query: str, resources: list[LearningResource], top_k: int = 3) -> list[dict]:
        chunks = self._build_chunks(resources)
        if not chunks:
            return []

        query_tokens = self._tokenize(query)
        document_frequency = self._document_frequency(chunks)
        average_length = sum(len(chunk.tokens) for chunk in chunks) / len(chunks)
        tfidf_query = Counter(query_tokens)
        scored = []
        for chunk in chunks:
            bm25 = self._score(query, query_tokens, chunk, document_frequency, len(chunks), average_length)
            tfidf = self._tfidf_cosine(tfidf_query, chunk.tokens, document_frequency, len(chunks))
            rerank = self._rerank(query, chunk)
            scored.append((bm25 * 0.65 + tfidf * 0.25 + rerank * 0.1, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)

        deduped: list[tuple[float, ResourceChunk]] = []
        seen_resources: set[str] = set()
        for score, chunk in scored:
            if chunk.resource.resource_id in seen_resources:
                continue
            seen_resources.add(chunk.resource.resource_id)
            deduped.append((score, chunk))
            if len(deduped) >= top_k:
                break

        return [
            {
                "resource_id": chunk.resource.resource_id,
                "chunk_id": chunk.chunk_id,
                "title": chunk.resource.title,
                "source_title": chunk.resource.title,
                "knowledge_points": list(chunk.resource.knowledge_points),
                "style": chunk.resource.style,
                "difficulty": chunk.resource.difficulty,
                "score": round(score, 4),
                "snippet": self._snippet(query, chunk.text),
            }
            for score, chunk in deduped
        ]

    def _build_chunks(self, resources: list[LearningResource]) -> list[ResourceChunk]:
        chunks: list[ResourceChunk] = []
        for resource in resources:
            base = (
                f"{resource.title}。知识点：{'、'.join(resource.knowledge_points)}。"
                f"形式：{resource.style}。难度：{resource.difficulty}。{resource.content}"
            )
            parts = self._split_text(base)
            for index, part in enumerate(parts, start=1):
                chunks.append(
                    ResourceChunk(
                        resource=resource,
                        chunk_id=f"{resource.resource_id}#{index}",
                        text=part,
                        tokens=tuple(self._tokenize(part)),
                    )
                )
        return chunks

    def _split_text(self, text: str, chunk_size: int = 80, overlap: int = 16) -> list[str]:
        clean = re.sub(r"\s+", " ", text).strip()
        if len(clean) <= chunk_size:
            return [clean]
        chunks = []
        start = 0
        while start < len(clean):
            end = min(len(clean), start + chunk_size)
            chunks.append(clean[start:end])
            if end == len(clean):
                break
            start = max(end - overlap, start + 1)
        return chunks

    def _tokenize(self, text: str) -> list[str]:
        lowered = text.lower()
        words = re.findall(r"[a-z0-9_]+", lowered)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
        return words + chinese_chars

    def _document_frequency(self, chunks: list[ResourceChunk]) -> Counter[str]:
        frequency: Counter[str] = Counter()
        for chunk in chunks:
            for token in set(chunk.tokens):
                frequency[token] += 1
        return frequency

    def _score(
        self,
        raw_query: str,
        query_tokens: list[str],
        chunk: ResourceChunk,
        document_frequency: Counter[str],
        total_documents: int,
        average_length: float,
    ) -> float:
        if not query_tokens:
            return chunk.resource.quality * 0.05

        counts = Counter(chunk.tokens)
        k1 = 1.5
        b = 0.75
        length = max(len(chunk.tokens), 1)
        score = 0.0
        for token in query_tokens:
            tf = counts[token]
            if tf == 0:
                continue
            df = document_frequency[token]
            idf = math.log(1 + (total_documents - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1 - b + b * length / max(average_length, 1))
            score += idf * (tf * (k1 + 1)) / denominator

        point_hit = 1.0 if raw_query in chunk.resource.knowledge_points else 0.0
        title_hit = 1.0 if raw_query in chunk.resource.title else 0.0
        return score + point_hit * 2.0 + title_hit * 0.8 + chunk.resource.quality * 0.1

    def _snippet(self, query: str, text: str, length: int = 90) -> str:
        index = text.find(query)
        if index < 0:
            return text[:length]
        start = max(0, index - 20)
        end = min(len(text), index + length)
        return text[start:end]

    def _tfidf_cosine(
        self,
        query_counts: Counter[str],
        document_tokens: tuple[str, ...],
        document_frequency: Counter[str],
        total_documents: int,
    ) -> float:
        if not query_counts or not document_tokens:
            return 0.0
        document_counts = Counter(document_tokens)
        shared = set(query_counts) & set(document_counts)
        if not shared:
            return 0.0

        def weight(token: str, count: int) -> float:
            idf = math.log(1 + total_documents / (1 + document_frequency[token]))
            return count * idf

        numerator = sum(weight(token, query_counts[token]) * weight(token, document_counts[token]) for token in shared)
        query_norm = math.sqrt(sum(weight(token, count) ** 2 for token, count in query_counts.items()))
        doc_norm = math.sqrt(sum(weight(token, count) ** 2 for token, count in document_counts.items()))
        return 0.0 if query_norm == 0 or doc_norm == 0 else numerator / (query_norm * doc_norm)

    def _rerank(self, query: str, chunk: ResourceChunk) -> float:
        score = 0.0
        if query in chunk.resource.knowledge_points:
            score += 1.0
        if query in chunk.resource.title:
            score += 0.6
        if query in chunk.text:
            score += 0.4
        return score
