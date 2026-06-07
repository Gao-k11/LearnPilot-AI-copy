from backend.app.adapters.llm_adapter import MockLLMAdapter


class ProfileAgent:
    name = "ProfileAgent"

    def __init__(self, llm: MockLLMAdapter | None = None) -> None:
        self.llm = llm or MockLLMAdapter()

    def run(self, text: str) -> dict:
        return self.llm.profile_from_text(text)
