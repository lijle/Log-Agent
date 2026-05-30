from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from llm.base_llm import BaseLLM
from memory.sqlite_memory import SQLiteMemory
from tools.tool_registry import ToolRegistry


class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        llm: BaseLLM,
        tool_registry: ToolRegistry,
        memory: SQLiteMemory | None = None,
    ) -> None:
        self.name = name
        self.llm = llm
        self.tool_registry = tool_registry
        self.memory = memory

    @abstractmethod
    def run(self, user_input: str) -> dict[str, Any]:
        raise NotImplementedError
