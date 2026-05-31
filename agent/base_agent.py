from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from llm.base_llm import BaseLLM
from memory.sqlite_memory import SQLiteMemory
from tools.tool_registry import ToolRegistry


class BaseAgent(ABC):
    """所有 Agent 的抽象基类。

    作用：
    - 统一持有 Agent 名称、LLM、工具注册表和记忆库引用
    - 约束子类必须实现 `run`
    - 让后续替换成别的 Agent 策略时仍能共用相同接口
    """

    def __init__(
        self,
        name: str,
        llm: BaseLLM,
        tool_registry: ToolRegistry,
        memory: SQLiteMemory | None = None,
    ) -> None:
        """初始化 Agent 共享依赖。

        作用：
        - 把运行 Agent 需要的核心对象保存到实例上

        输入：
        - name：Agent 名称，方便标识当前实现
        - llm：LLM 抽象实例，可能是真实模型或 FakeLLM
        - tool_registry：工具注册中心
        - memory：可选的记忆库实现，这个项目里通常是 SQLiteMemory

        输出：
        - None
        """

        self.name = name
        self.llm = llm
        self.tool_registry = tool_registry
        self.memory = memory

    @abstractmethod
    def run(self, user_input: str) -> dict[str, Any]:
        """执行一次 Agent 任务。

        作用：
        - 定义所有 Agent 子类统一的运行入口

        输入：
        - user_input：用户输入，当前项目中通常是原始日志文本

        输出：
        - dict[str, Any]：结构化执行结果，由具体 Agent 子类定义
        """

        raise NotImplementedError
