from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_service.content_generator import QwenMaxClient, load_dotenv_if_present


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    load_dotenv_if_present()
    os.environ["LEARNPILOT_LLM_MODE"] = "auto"
    if not (os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")):
        raise SystemExit("请先设置 DASHSCOPE_API_KEY 或 QWEN_API_KEY。")

    client = QwenMaxClient.from_env()
    if client is None:
        raise SystemExit("Qwen 客户端初始化失败。")

    result = client.generate(
        "请返回 JSON：{\"title\":\"Qwen 连通性测试\",\"explanation\":\"一句话说明连接成功\"}"
    )
    print(json.dumps({"model": client.model, "result": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
