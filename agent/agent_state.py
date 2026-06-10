from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentStep:
    """记录一次 ReAct 步骤。

    输入：
    - thought: 这一轮为什么要做这个动作
    - action: 这一轮调用的工具名
    - action_input: 传给工具的结构化输入
    - observation: 工具返回结果
    """

    thought: str
    action: str
    action_input: dict[str, Any]
    observation: dict[str, Any]


@dataclass
class AgentState:
    """保存一次 Agent 运行过程中的完整状态。

    可以把它理解成 Agent 的工作记忆：
    - user_input: 用户原始日志
    - parsed_result: 日志解析结果
    - rag_result: 知识库检索结果
    - memory_result: 历史案例检索结果
    - report_result: 最终诊断报告结果
    - missing_evidence: 当前仍缺失的关键证据
    """

    user_input: str
    steps: list[AgentStep] = field(default_factory=list)
    final_answer: dict[str, Any] = field(default_factory=dict)

    parsed_result: dict[str, Any] = field(default_factory=dict)
    rag_result: dict[str, Any] = field(default_factory=dict)
    memory_result: dict[str, Any] = field(default_factory=dict)
    memory_write_result: dict[str, Any] = field(default_factory=dict)
    report_result: dict[str, Any] = field(default_factory=dict)

    missing_evidence: list[str] = field(default_factory=list)
    last_decision_source: str = "rule"

    is_finished: bool = False
    iteration_count: int = 0

    def add_step(
        self,
        thought: str,
        action: str,
        action_input: dict[str, Any],
        observation: dict[str, Any],
    ) -> None:
        """追加一步执行记录，供前端展示 Thought / Action / Observation。"""

        self.steps.append(
            AgentStep(
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
            )
        )
