from __future__ import annotations

from typing import Any, TypedDict

class GraphState(TypedDict, total=False):
    """LangGraph 共享状态。

    这份状态会在多个节点之间不断传递和更新。
    你可以把它理解成 LangGraph 版本的 AgentState。
    """

    # 原始输入
    user_input: str

    # 各阶段中间结果
    parsed_result: dict[str, Any]
    tempo_result: dict[str, Any]
    rag_result: dict[str, Any]
    memory_result: dict[str, Any]
    report_result: dict[str, Any]
    memory_write_result: dict[str, Any]

    # 状态评估相关
    missing_evidence: list[str]
    iteration_count: int
    is_finished: bool

    # 过程可视化
    trace: list[dict[str, Any]]

    next_action: str

    # 标记这次是 "llm" 决策，还是 "rule" 兜底
    decision_source: str
    # 把 LLM 原始输出留下来，方便你以后排查 prompt/解析问题
    llm_raw_output: str

    report_llm_source: str