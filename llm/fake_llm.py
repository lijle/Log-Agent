from __future__ import annotations

from llm.base_llm import BaseLLM


class FakeLLM(BaseLLM):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return (
            "LLM fallback mode is active. "
            "Please use deterministic report generation based on the provided evidence."
        )
