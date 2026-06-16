from __future__ import annotations

from agent.langgraph_state import GraphState

def route_after_parse(state: GraphState) -> str:
    """parse_log_node 执行完后的下一跳。

    现在最简单直接的设计是：
    - parse 完日志后，一定先进入证据评估阶段
    """
    return "assess_evidence_node"

def route_after_assess(state: GraphState) -> str:
    """根据 assess_evidence_node 产出的 next_action 跳转。"""

    next_action = state.get("next_action", "")

    if next_action in {
        "retrieve_knowledge_node",
        "search_memory_node",
        "generate_report_node",
    }:
        return next_action

    return "generate_report_node"

def _is_ready_to_answer(state: GraphState) -> bool:
    """判断当前证据是否足够进入最终报告阶段。"""
    parsed = state.get("parsed_result", {}).get("extracted_fields", {})
    if not parsed:
        return False

    core_fields = [
        parsed.get("service_name"),
        parsed.get("exception_type"),
        parsed.get("error_message"),
    ]
    core_score = sum(1 for item in core_fields if item)

    has_knowledge = bool(state.get("rag_result", {}).get("documents"))
    has_history = bool(state.get("memory_result", {}).get("cases"))

    return core_score >= 2 and (has_knowledge or has_history)


