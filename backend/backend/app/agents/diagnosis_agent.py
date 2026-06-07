from backend.app.adapters.ml_adapter import MockMLAdapter


class DiagnosisAgent:
    name = "DiagnosisAgent"

    def __init__(self, ml: MockMLAdapter | None = None) -> None:
        self.ml = ml or MockMLAdapter()

    def run(self, profile: dict) -> list[dict]:
        return self.ml.diagnose_weakness(profile)
