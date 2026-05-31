from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentStep:
    """保存一次 ReAct 步骤的最小单元。

    作用：
    - 记录 Agent 当时的 thought
    - 记录调用了哪个 action
    - 记录 action 的输入和返回结果
    - 供页面上的“Agent 执行轨迹”直接展示
    """

    thought: str
    action: str
    action_input: dict[str, Any]
    observation: dict[str, Any]


@dataclass
class AgentState:
    """保存一次 Agent 运行过程中的上下文状态。

    作用：
    - 记录本次用户输入的原始日志
    - 维护按顺序追加的步骤列表
    - 保存最终汇总答案
    """

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
        """向状态中追加一条执行步骤。

        作用：
        - 在每次工具执行后生成一个 AgentStep
        - 保证前端能按时间顺序展示整个推理过程

        输入：
        - thought：当前步骤的思考说明
        - action：调用的工具名
        - action_input：工具输入
        - observation：工具输出

        输出：
        - None：结果直接写入 `self.steps`
        """

        self.steps.append(
            AgentStep(
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
            )
        )
