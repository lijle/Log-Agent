from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """所有工具的抽象基类。

    作用：
    - 约束每个工具都要提供 name、description 和 run
    - 让 ToolRegistry 和 Agent 可以用统一方式调用工具
    """

    name: str
    description: str

    @abstractmethod
    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """执行工具逻辑。

        作用：
        - 接收结构化输入
        - 返回结构化输出

        输入：
        - input：工具所需的参数字典

        输出：
        - dict[str, Any]：工具执行结果
        """

        raise NotImplementedError
