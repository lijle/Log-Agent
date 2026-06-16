from __future__ import annotations

from typing import Any

from langgraph.graph import END,START,StateGraph

from agent.langgraph_nodes import (
    assess_evidence_node,
    generate_report_node,
    parse_log_node,
    persist_case_node,
    retrieve_knowledge_node,
    search_memory_node,
)

from agent.langgraph_router import route_after_assess, route_after_parse
from agent.langgraph_state import GraphState

class LangGraphAgent:
    """基于 LangGraph 的日志诊断 Agent。

    这个类负责把“节点 + 路由规则 + 状态”编译成一张真正可运行的图。
    你可以把它理解成：
    - ReActAgent 是 while 循环版 Agent
    - LangGraphAgent 是状态图版 Agent
    """

    def __init__(self) -> None:
        """初始化并编译 LangGraph。"""
        self.graph = self._build_graph().compile()

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 工作流。

        图结构：
        START
          -> parse_log_node
          -> assess_evidence_node
             -> retrieve_knowledge_node / search_memory_node / generate_report_node
          -> persist_case_node
          -> END
        """

        workflow = StateGraph(GraphState)

        workflow.add_node("parse_log_node", parse_log_node)
        workflow.add_node("assess_evidence_node", assess_evidence_node)
        workflow.add_node("retrieve_knowledge_node", retrieve_knowledge_node)
        workflow.add_node("search_memory_node", search_memory_node)
        workflow.add_node("generate_report_node", generate_report_node)
        workflow.add_node("persist_case_node", persist_case_node)

        workflow.add_edge(START, "parse_log_node")

        workflow.add_conditional_edges("parse_log_node",route_after_parse)
        workflow.add_conditional_edges("assess_evidence_node",route_after_assess)

        workflow.add_edge("retrieve_knowledge_node", "assess_evidence_node")
        workflow.add_edge("search_memory_node", "assess_evidence_node")
        workflow.add_edge("generate_report_node", "persist_case_node")
        workflow.add_edge("persist_case_node", END)

        return workflow

    def run(self, user_input: str) -> dict[str, Any]:
        """执行 LangGraph Agent。

        输入：
        - user_input: 用户提交的原始日志文本

        输出：
        - 一个和现有 ReActAgent 尽量接近的结果字典，
          方便后续 UI 层低成本切换
        """
        initial_state: GraphState = {
            "user_input": user_input,
            "parsed_result": {},
            "rag_result": {},
            "memory_result": {},
            "report_result": {},
            "memory_write_result": {},
            "missing_evidence": [],
            "iteration_count": 0,
            "is_finished": False,
            "trace": [],
        }

        final_state = self.graph.invoke(initial_state)

        report_result = final_state.get("report_result", {})

        return {
            "parsed_result": final_state.get("parsed_result", {}),
            "rag_result": final_state.get("rag_result", {}),
            "memory_result": final_state.get("memory_result", {}),
            "report_result": report_result,
            "report_markdown": report_result.get("report_markdown", ""),
            "memory_write_result": final_state.get("memory_write_result", {}),
            "decision_source": final_state.get("decision_source", ""),
            "llm_raw_output": final_state.get("llm_raw_output", ""),
            "report_llm_source": final_state.get("report_llm_source", ""),
            "trace": final_state.get("trace", []),
        }