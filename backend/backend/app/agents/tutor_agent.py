from backend.app.adapters.llm_adapter import MockLLMAdapter


class TutorAgent:
    name = "TutorAgent"

    def __init__(self, llm: MockLLMAdapter | None = None) -> None:
        self.llm = llm or MockLLMAdapter()

    def run(
        self,
        question: str,
        profile: dict | None = None,
        history: list[str] | None = None,
        evidence: list[dict] | None = None,
    ) -> dict:
        return self.llm.tutor_answer(question, profile, history, evidence)
