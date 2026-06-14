from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import InteractionEvent, KnowledgeNode, LearningResource, Recommendation, StudentProfile
from .recommender import ResourceRecommender


FEATURE_VERSION = "learning-ranker-v1"
DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "artifacts"
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")


@dataclass(frozen=True)
class RankerMeta:
    model_type: str
    feature_version: str
    trained_at: str | None
    samples: int
    metrics: dict[str, float]
    fallback_reason: str | None = None


class RankingFeatureExtractor:
    def __init__(self, knowledge_graph: list[KnowledgeNode] | None = None) -> None:
        self.knowledge_graph = {node.name: node for node in knowledge_graph or []}

    def extract(
        self,
        profile: StudentProfile,
        resource: LearningResource,
        history: list[InteractionEvent] | None = None,
    ) -> dict[str, float]:
        history = history or []
        weakness = self._weakness(profile, resource)
        difficulty_gap = abs(profile.target_difficulty - resource.difficulty)
        style_preference = 1.0 if resource.style in profile.preferred_styles else 0.0
        duration_fit = 1.0 if resource.estimated_minutes <= 25 else 0.75 if resource.estimated_minutes <= 45 else 0.45
        graph_distance = self._graph_distance(resource.knowledge_points, profile.weak_points)
        positive_feedback = self._feedback_ratio(history, resource, liked=True)
        negative_feedback = self._feedback_ratio(history, resource, liked=False)
        novelty = 0.0 if any(event.resource_id == resource.resource_id for event in history) else 1.0
        return {
            "weakness": round(weakness, 6),
            "difficulty_fit": round(1.0 - difficulty_gap, 6),
            "style_preference": style_preference,
            "quality": resource.quality,
            "duration_fit": duration_fit,
            "graph_distance_fit": round(1.0 / (1.0 + graph_distance), 6),
            "positive_feedback": positive_feedback,
            "negative_feedback": negative_feedback,
            "novelty": novelty,
            "engagement": profile.engagement_score,
            "forgetting_risk": profile.forgetting_risk,
        }

    def feature_names(self) -> list[str]:
        return [
            "weakness",
            "difficulty_fit",
            "style_preference",
            "quality",
            "duration_fit",
            "graph_distance_fit",
            "positive_feedback",
            "negative_feedback",
            "novelty",
            "engagement",
            "forgetting_risk",
        ]

    def _weakness(self, profile: StudentProfile, resource: LearningResource) -> float:
        if not resource.knowledge_points:
            return 0.0
        return sum(1.0 - profile.mastery.get(point, 0.5) for point in resource.knowledge_points) / len(resource.knowledge_points)

    def _graph_distance(self, points: tuple[str, ...], weak_points: list[str]) -> float:
        if not weak_points:
            return 1.0
        if set(points) & set(weak_points):
            return 0.0
        prerequisites = set()
        for point in points:
            prerequisites.update(self.knowledge_graph.get(point, KnowledgeNode(point)).prerequisites)
        return 1.0 if prerequisites & set(weak_points) else 2.0

    def _feedback_ratio(self, history: list[InteractionEvent], resource: LearningResource, liked: bool) -> float:
        related = [
            event
            for event in history
            if event.resource_id == resource.resource_id or set(event.knowledge_points) & set(resource.knowledge_points)
        ]
        if not related:
            return 0.0
        hits = [event for event in related if event.liked is liked or ((event.score or 0.0) >= 0.7) is liked]
        return round(len(hits) / len(related), 6)


class TrainableRanker:
    def __init__(
        self,
        artifact_dir: Path | None = None,
        knowledge_graph: list[KnowledgeNode] | None = None,
    ) -> None:
        self.artifact_dir = artifact_dir or DEFAULT_ARTIFACT_DIR
        self.extractor = RankingFeatureExtractor(knowledge_graph)
        self.model: Any | None = None
        self.weights: dict[str, float] | None = None
        self.meta = RankerMeta(
            model_type="rule",
            feature_version=FEATURE_VERSION,
            trained_at=None,
            samples=0,
            metrics={},
            fallback_reason="no trained artifact loaded",
        )
        self._load()

    def recommend(
        self,
        profile: StudentProfile,
        resources: list[LearningResource],
        top_k: int,
        history: list[InteractionEvent] | None = None,
    ) -> list[Recommendation]:
        if not resources:
            return []
        scored = []
        rule_recommender = ResourceRecommender()
        for resource in resources:
            features = self.extractor.extract(profile, resource, history)
            model_score = self._predict_score(features)
            rule_score = rule_recommender.score_resource(profile, resource).score
            score = self._blend_score(model_score, rule_score)
            reasons = (
                f"模型评分 {score:.3f}",
                f"薄弱度 {features['weakness']:.2f}",
                f"难度适配 {features['difficulty_fit']:.2f}",
            )
            scored.append(Recommendation(resource=resource, score=round(score, 4), reasons=reasons, features=features))
        scored.sort(key=lambda item: item.score, reverse=True)
        return ResourceRecommender()._diversify(scored, top_k)

    def status(self) -> dict:
        return asdict(self.meta)

    def _predict_score(self, features: dict[str, float]) -> float:
        if self.model is not None:
            try:
                values = _feature_frame([features], self.extractor.feature_names())
                if hasattr(self.model, "predict_proba"):
                    return float(self.model.predict_proba(values)[0][1])
                return float(self.model.predict(values)[0])
            except Exception:
                pass
        if self.weights:
            bias = self.weights.get("bias", 0.0)
            raw = bias + sum(self.weights.get(name, 0.0) * features[name] for name in self.extractor.feature_names())
            return 1.0 / (1.0 + math.exp(-raw))
        return (
            features["weakness"] * 0.32
            + features["difficulty_fit"] * 0.18
            + features["style_preference"] * 0.12
            + features["quality"] * 0.12
            + features["duration_fit"] * 0.06
            + features["graph_distance_fit"] * 0.08
            + features["positive_feedback"] * 0.08
            - features["negative_feedback"] * 0.06
            + features["novelty"] * 0.04
        )

    def _blend_score(self, model_score: float, rule_score: float) -> float:
        if self.meta.model_type == "lightgbm-classifier":
            return model_score * 0.25 + rule_score * 0.75
        if self.meta.model_type.startswith("sklearn"):
            return model_score * 0.2 + rule_score * 0.8
        if self.meta.model_type == "weighted-fallback":
            return model_score * 0.15 + rule_score * 0.85
        return rule_score

    def _load(self) -> None:
        meta_path = self.artifact_dir / "ranker_meta.json"
        weights_path = self.artifact_dir / "ranker_weights.json"
        model_path = self.artifact_dir / "ranker_model.joblib"
        if meta_path.exists():
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            self.meta = RankerMeta(**data)
        if model_path.exists():
            try:
                import joblib

                self.model = joblib.load(model_path)
                return
            except Exception as exc:
                self.meta = RankerMeta(
                    **{**asdict(self.meta), "fallback_reason": f"joblib model load failed: {exc}"}
                )
        if weights_path.exists():
            self.weights = json.loads(weights_path.read_text(encoding="utf-8"))


def train_ranker_artifacts(
    rows: list[tuple[dict[str, float], int]],
    artifact_dir: Path | None = None,
) -> dict:
    artifact_dir = artifact_dir or DEFAULT_ARTIFACT_DIR
    artifact_dir.mkdir(parents=True, exist_ok=True)
    feature_names = RankingFeatureExtractor().feature_names()
    x = _feature_frame([features for features, _ in rows], feature_names)
    y = [label for _, label in rows]
    model_type = "sklearn-logistic"
    metrics: dict[str, float]
    fallback_reason = None

    try:
        try:
            from lightgbm import LGBMClassifier

            model = LGBMClassifier(n_estimators=80, learning_rate=0.05, random_state=42)
            model_type = "lightgbm-classifier"
        except Exception as exc:
            fallback_reason = f"lightgbm unavailable: {exc}"
            from sklearn.tree import DecisionTreeClassifier

            model = DecisionTreeClassifier(max_depth=6, min_samples_leaf=8, random_state=42)
            model_type = "sklearn-decision-tree"
        model.fit(x, y)
        predictions = model.predict_proba(x)[:, 1] if hasattr(model, "predict_proba") else model.predict(x)
        metrics = _binary_metrics(y, [float(item) for item in predictions])
        import joblib

        joblib.dump(model, artifact_dir / "ranker_model.joblib")
    except Exception as exc:
        model_type = "weighted-fallback"
        fallback_reason = f"training failed: {exc}"
        weights = _fit_simple_weights(rows, feature_names)
        predictions = [_sigmoid(weights.get("bias", 0.0) + sum(weights.get(name, 0.0) * features[name] for name in feature_names)) for features, _ in rows]
        metrics = _binary_metrics(y, predictions)
        (artifact_dir / "ranker_weights.json").write_text(json.dumps(weights, indent=2), encoding="utf-8")

    meta = RankerMeta(
        model_type=model_type,
        feature_version=FEATURE_VERSION,
        trained_at=datetime.now(timezone.utc).isoformat(),
        samples=len(rows),
        metrics=metrics,
        fallback_reason=fallback_reason,
    )
    (artifact_dir / "ranker_meta.json").write_text(json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8")
    return asdict(meta)


def _binary_metrics(y: list[int], scores: list[float]) -> dict[str, float]:
    if not y:
        return {"accuracy": 0.0, "auc_proxy": 0.0}
    predictions = [1 if score >= 0.5 else 0 for score in scores]
    accuracy = sum(int(pred == label) for pred, label in zip(predictions, y)) / len(y)
    positives = [score for score, label in zip(scores, y) if label == 1]
    negatives = [score for score, label in zip(scores, y) if label == 0]
    if not positives or not negatives:
        auc_proxy = accuracy
    else:
        pairs = [(pos > neg) + 0.5 * (pos == neg) for pos in positives for neg in negatives]
        auc_proxy = sum(pairs) / len(pairs)
    return {"accuracy": round(accuracy, 4), "auc_proxy": round(auc_proxy, 4)}


def _fit_simple_weights(rows: list[tuple[dict[str, float], int]], feature_names: list[str]) -> dict[str, float]:
    weights = {"bias": -0.2}
    for name in feature_names:
        pos = [features[name] for features, label in rows if label == 1]
        neg = [features[name] for features, label in rows if label == 0]
        weights[name] = (sum(pos) / max(len(pos), 1)) - (sum(neg) / max(len(neg), 1))
    return weights


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _feature_frame(rows: list[dict[str, float]], feature_names: list[str]):
    values = [[features[name] for name in feature_names] for features in rows]
    try:
        import pandas as pd

        return pd.DataFrame(values, columns=feature_names)
    except Exception:
        return values
