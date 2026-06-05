from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_service.profiler import StudentProfiler
from ml_service.ranker import RankingFeatureExtractor, train_ranker_artifacts
from ml_service.synthetic import load_synthetic_dataset


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    data_dir = ROOT / "data" / "generated"
    graph, resources, students, events = load_synthetic_dataset(data_dir)
    resources_by_id = {resource.resource_id: resource for resource in resources}
    events_by_student: dict[str, list] = {}
    for event in events:
        events_by_student.setdefault(event.student_id, []).append(event)
    extractor = RankingFeatureExtractor(graph)
    rows = []
    profiler = StudentProfiler()
    for student in students:
        history = events_by_student.get(student["student_id"], [])
        profile = profiler.build_profile(
            student_id=student["student_id"],
            diagnostics=student["diagnostics"],
            events=history[:3],
            goals=student.get("goals", []),
            preferred_styles=student.get("preferred_styles", []),
        )
        positive_ids = {event.resource_id for event in history if (event.score or 0.0) >= 0.68 or event.liked is True}
        negative_ids = {event.resource_id for event in history if (event.score or 0.0) < 0.45 or event.liked is False}
        for rid in list(positive_ids)[:4]:
            resource = resources_by_id.get(rid)
            if resource:
                rows.append((extractor.extract(profile, resource, history), 1))
        for rid in list(negative_ids)[:4]:
            resource = resources_by_id.get(rid)
            if resource:
                rows.append((extractor.extract(profile, resource, history), 0))
    meta = train_ranker_artifacts(rows, ROOT / "artifacts")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
