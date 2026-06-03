from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_service import InteractionEvent, LearningMLPipeline


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    pipeline = LearningMLPipeline()
    result = pipeline.recommend(
        student_id="stu_001",
        diagnostics={"变量": 0.9, "条件判断": 0.62, "循环": 0.42, "函数": 0.35, "列表": 0.4},
        events=[
            InteractionEvent(
                student_id="stu_001",
                resource_id="r003",
                knowledge_points=("循环",),
                score=0.5,
                completed=True,
                dwell_seconds=720,
                liked=True,
            )
        ],
        goals=["两周内完成 Python 入门项目"],
        preferred_styles=["example", "quiz"],
        top_k=5,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
