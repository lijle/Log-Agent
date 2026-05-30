from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentStep:
    thought: str
    action: str
    action_input: dict[str, Any]
    observation: dict[str, Any]


@dataclass
class AgentState:
    user_input: str
    steps: list[AgentStep] = field(default_factory=list)
    final_answer: dict[str, Any] = field(default_factory=dict)

    def add_step(
        self,
        thought: str,
        action: str,
        action_input: dict[str, Any],
        observation: dict[str, Any],
    ) -> None:
        self.steps.append(
            AgentStep(
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
            )
        )
