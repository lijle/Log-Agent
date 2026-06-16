from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# LLM 在 ReAct 决策阶段只允许选择这三个工具。
ALLOWED_REACT_ACTIONS = {
    "log_parser_tool",
    "rag_tool",
    "memory_tool",
}

# 当 LLM 认为证据已经足够时，需要输出这个结束信号。
FINAL_READY_SIGNAL = "READY_TO_REPORT"


@dataclass
class ReActDecision:
    """表示一轮 ReAct 决策结果。

    这个对象是 Agent 与 LLM 决策结果之间的统一协议。

    两种典型场景：
    1. 继续调用工具
       - thought: 为什么这么做
       - action: 工具名
       - action_input: 工具输入
    2. 结束搜证，进入报告阶段
       - thought: 为什么证据已经足够
       - final_answer: READY_TO_REPORT
    """

    thought: str
    action: str | None = None
    action_input: dict[str, Any] = field(default_factory=dict)
    final_answer: str | None = None

    @property
    def is_final(self) -> bool:
        """判断这轮决策是否表示“结束工具调用，进入报告阶段”。

        输出：
        - bool: True 表示当前应停止继续搜证，转入 report_tool
        """

        return self.final_answer == FINAL_READY_SIGNAL

    @property
    def is_action(self) -> bool:
        """判断这轮决策是否是一次合法工具调用。

        输出：
        - bool: True 表示 action 在白名单中
        """

        return self.action in ALLOWED_REACT_ACTIONS
