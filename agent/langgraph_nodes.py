from __future__ import annotations

from typing import Any

from agent.langgraph_state import GraphState
from parser.log_parser import parse_log

from pathlib import Path

from tools.rag_tool import RAGTool

from tools.memory_tool import MemoryTool
from memory.sqlite_memory import SQLiteMemory

from llm.fake_llm import FakeLLM
from tools.report_tool import ReportTool

from agent.react_parser import parse_react_output
from agent.react_prompts import REACT_SYSTEM_PROMPT, build_react_user_prompt
from agent.react_schema import ReActDecision
from llm.openai_compatible_llm import OpenAICompatibleLLM


KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"
DB_PATH = Path(__file__).resolve().parent.parent / "db" / "diagnosis_history.db"


def collect_missing_evidence(state: GraphState) -> list[str]:
    """根据当前状态评估还缺哪些关键证据。"""
    missing: list[str] = []
    fields = state.get("parsed_result", {}).get("extracted_fields", {})

    if not fields.get("service_name"):
        missing.append("service_name")
    if not fields.get("exception_type"):
        missing.append("exception_type")
    if not fields.get("error_message"):
        missing.append("error_message")
    if not state.get("rag_result", {}).get("documents"):
        missing.append("knowledge")
    if not state.get("memory_result", {}).get("cases"):
        missing.append("history")

    return missing

def decide_next_action_with_rules(state: GraphState) -> str:
    """根据当前状态决定下一步节点。

    当前先使用规则版决策，后面会升级成 Agent / LLM 决策。
    """
    rag_result = state.get("rag_result", {})
    memory_result = state.get("memory_result", {})

    if not rag_result:
        return "retrieve_knowledge_node"
    if not memory_result:
        return "search_memory_node"

    return "generate_report_node"

def decide_next_action_with_llm(state: GraphState) -> tuple[str | None, str]:
    """尝试使用 LLM / ReAct 方式决定下一步动作。

    返回：
    - next_action: 决策出的下一个节点名；如果失败则返回 None
    - llm_raw_output: LLM 原始输出文本，失败时尽量保留，便于排查
    """
    llm = OpenAICompatibleLLM.from_env()
    if llm is None:
        return None, ""

    state_summary = build_graph_state_summary(state)
    tools_text = build_tools_text()

    user_prompt = build_react_user_prompt(
        user_input=state.get("user_input",""),
        state_summary=state_summary,
        tools_text=tools_text,
    )

    try:
        raw_output = llm.generate(
            system_prompt=REACT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        decision = parse_react_output(raw_output)

        if not is_valid_graph_decision(decision):
            return None, raw_output

        next_action = map_react_action_to_graph_node(decision)
        return next_action, raw_output
    except Exception:
        return None, ""





def assess_evidence_node(state: GraphState) -> dict[str, Any]:
    """LangGraph 节点：评估当前证据，并决定下一步动作。

    决策顺序：
    1. 先尝试让 LLM 按 ReAct 方式决定下一步
    2. 如果 LLM 不可用、输出非法或解析失败，则回退到规则版决策
    """
    missing_evidence = collect_missing_evidence(state)
    llm_next_action, llm_raw_output = decide_next_action_with_llm(state)

    if llm_next_action:
        next_action = llm_next_action
        decision_source = "llm"
        thought = (
            f"Agent 根据当前状态决定下一步前往 {next_action}。"
        )
    else:
        next_action = decide_next_action_with_rules(state)
        decision_source = "rule"
        thought = (
            f"LLM 决策不可用或不合法，回退到规则决策，下一步前往 {next_action}。"
        )

    trace_entry = {
        "thought": thought,
        "action": "assess_evidence",
        "action_input": {},
        "observation": {
            "missing_evidence": missing_evidence,
            "next_action": next_action,
            "decision_source": decision_source,
            "llm_raw_output": llm_raw_output,
        },
    }
    current_trace = state.get("trace", [])

    return {
        "missing_evidence": missing_evidence,
        "next_action": next_action,
        "decision_source": decision_source,
        "llm_raw_output": llm_raw_output,
        "trace": current_trace + [trace_entry],
    }



def parse_log_node(state: GraphState) -> dict[str, Any]:
    """LangGraph 节点：解析原始日志。

    输入：
    - state["user_input"]: 原始日志文本

    输出：
    - parsed_result: 日志结构化结果
    - missing_evidence: 当前仍缺失的证据
    - trace: 追加一条执行记录
    """
    raw_log = state.get("user_input", "")
    parsed_result = parse_log(raw_log)

    trace_entry = {
        "thought": "先解析原始日志，提取关键字段。",
        "action": "log_parser_tool",
        "action_input": {"raw_log": raw_log},
        "observation": parsed_result,
    }

    current_trace = state.get("trace", [])

    temp_state: GraphState = {
        **state,
        "parsed_result": parsed_result,
    }

    return {
        "parsed_result": parsed_result,
        "missing_evidence": collect_missing_evidence(temp_state),
        "iteration_count": state.get("iteration_count", 0) + 1,
        "trace": current_trace + [trace_entry],
    }

def extract_rag_keywords(parsed_result: dict[str, Any]) -> list[str]:
    """从日志解析结果中提取更适合知识库检索的补充关键词。用来构建更好的query"""
    fields = parsed_result.get("extracted_fields", {})
    error_message = str(fields.get("error_message", "")).lower()

    keywords: list[str] = []
    if "timeout" in error_message:
        keywords.append("timeout")
    if "connection" in error_message:
        keywords.append("connection")
    if "connection is not available" in error_message:
        keywords.append("database connection unavailable")
    if "hikaripool" in error_message or "pool" in error_message:
        keywords.append("connection pool")
    if "auth" in error_message or "token" in error_message:
        keywords.append("authentication")
    if "nullpointerexception" in error_message or "null pointer" in error_message:
        keywords.append("null pointer")
    if "refused" in error_message:
        keywords.append("connection refused")
    # 去重，同时保持顺序
    deduplicated: list[str] = []
    for item in keywords:
        if item and item not in deduplicated:
            deduplicated.append(item)

    return deduplicated

def build_rag_query(parsed_result: dict[str, Any]) -> str:
    """基于日志解析结果构造更适合知识库检索的查询语句。"""
    fields = parsed_result.get("extracted_fields", {})

    exception_type = str(fields.get("exception_type", "")).strip()
    error_message = str(fields.get("error_message", "")).strip()
    service_name = str(fields.get("service_name", "")).strip()
    status_code = fields.get("http_status_code")
    log_summary = str(parsed_result.get("log_summary", "")).strip()

    keyword_hints = extract_rag_keywords(parsed_result)

    parts: list[str] = []

    if exception_type:
        parts.append(exception_type)
    condensed_error_message = error_message
    if ":" in condensed_error_message:
        condensed_error_message = condensed_error_message.split(":", 1)[1].strip()
    if condensed_error_message:
        parts.append(condensed_error_message)
    if service_name:
        parts.append(service_name)

    parts.extend(keyword_hints)

    # 只有在关键信息较少时，才回退使用更长的日志摘要做兜底。
    if log_summary and len(parts) < 3:
        parts.append(log_summary)
    if status_code:
        parts.append(f"http {status_code}")
    # 去重并去空
    normalized_parts: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = part.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            normalized_parts.append(cleaned)
            seen.add(key)

    return " ".join(normalized_parts)

def retrieve_knowledge_node(state: GraphState) -> dict[str, Any]:
    """LangGraph 节点：检索知识库。

    输入：
    - state["parsed_result"]: 日志结构化结果

    输出：
    - rag_result: 知识库检索结果
    - missing_evidence: 更新后的缺失证据
    - trace: 追加一条执行记录
    """
    parsed_result = state.get("parsed_result", {})
    query = build_rag_query(parsed_result)

    rag_tool = RAGTool(knowledge_base_dir=KNOWLEDGE_BASE_DIR)
    rag_result = rag_tool.run({"query": query, "top_k": 4, "candidate_k": 8})

    trace_entry = {
        "thought": "已经拿到异常类型、错误信息和日志摘要，检索知识库补充排障背景。",
        "action": "rag_tool",
        "action_input": {"query": query, "top_k": 4, "candidate_k": 8},
        "observation": rag_result,
    }
    current_trace = state.get("trace", [])

    temp_state: GraphState = {
        **state,
        "rag_result": rag_result,
    }

    return {
        "rag_result": rag_result,
        "missing_evidence": collect_missing_evidence(temp_state),
        "iteration_count": state.get("iteration_count", 0) + 1,
        "trace": current_trace + [trace_entry],
    }

def build_memory_query(parsed_result: dict[str, Any]) -> str:
    """基于日志解析结果构造历史案例搜索语句。"""

    fields = parsed_result.get("extracted_fields", {})
    parts = [
        fields.get("service_name", ""),
        fields.get("exception_type", ""),
        fields.get("error_message", ""),
        parsed_result.get("log_summary", ""),
    ]
    return " ".join(part for part in parts if part)

def build_tools_text()->str:
    """构造提供给 ReAct 决策模型的工具说明文本。即描述目前存在tool的功能和作用，对tool的说明"""
    return "\n".join([
        "- log_parser_tool: Parse raw application logs and extract structured error fields.",
        "- rag_tool: Retrieve relevant troubleshooting knowledge from local markdown documents.",
        '- memory_tool: Search historical diagnosis cases in SQLite using {"action": "search_cases", "query": "...", "limit": 3}.',
    ])

def build_graph_state_summary(state: GraphState) -> dict[str, Any]:
    """把当前 GraphState 整理成适合给 LLM 阅读的摘要。"""
    return{
        "iteration_count": state.get("iteration_count", 0),
        "parsed_result": state.get("parsed_result", {}),
        "rag_result_summary": {
            "query": state.get("rag_result", {}).get("query"),
            "document_count": len(state.get("rag_result", {}).get("documents", [])),
        },
        "memory_result_summary": {
            "case_count": len(state.get("memory_result", {}).get("cases", [])),
        },
        "missing_evidence": collect_missing_evidence(state),
        "executed_steps": [
            {
                "action": step.get("action"),
                "action_input": step.get("action_input", {}),
            }
            for step in state.get("trace", [])
        ],
    }


def is_valid_graph_decision(decision: ReActDecision) -> bool:
    """校验 LLM 决策是否可执行。"""
    if decision.is_final:
        return True

    if not decision.is_action:
        return False

    if not isinstance(decision.action_input, dict):
        return False

    if decision.action == "log_parser_tool":
        return "raw_log" in decision.action_input

    if decision.action == "rag_tool":
        return "query" in decision.action_input

    if decision.action == "memory_tool":
        return (
            decision.action_input.get("action") == "search_cases"
            and "query" in decision.action_input
        )

    return False

def map_react_action_to_graph_node(decision: ReActDecision) -> str:
    """把 ReAct 工具动作映射成 LangGraph 节点名。"""
    if decision.is_final:
        return "generate_report_node"

    if decision.action == "log_parser_tool":
        return "parse_log_node"

    if decision.action == "rag_tool":
        return "retrieve_knowledge_node"

    if decision.action == "memory_tool":
        return "search_memory_node"

    return "generate_report_node"

def search_memory_node(state: GraphState) -> dict[str, Any]:
    """LangGraph 节点：搜索历史案例。

    输入：
    - state["parsed_result"]: 日志结构化结果

    输出：
    - memory_result: 历史案例搜索结果
    - missing_evidence: 更新后的缺失证据
    - trace: 追加一条执行记录
    """
    parsed_result = state.get("parsed_result", {})
    query = build_memory_query(parsed_result)

    memory_store = SQLiteMemory(DB_PATH)
    memory_tool = MemoryTool(memory_store=memory_store)
    memory_result = memory_tool.run(
        {
            "action": "search_cases",
            "query": query,
            "limit": 3,
        }
    )
    trace_entry = {
        "thought": "当前已经知道服务名或异常类型，继续搜索历史案例，看看是否有相似问题。",
        "action": "memory_tool",
        "action_input": {
            "action": "search_cases",
            "query": query,
            "limit": 3,
        },
        "observation": memory_result,
    }
    current_trace = state.get("trace", [])

    temp_state: GraphState = {
        **state,
        "memory_result": memory_result,
    }

    return {
        "memory_result": memory_result,
        "missing_evidence": collect_missing_evidence(temp_state),
        "iteration_count": state.get("iteration_count", 0) + 1,
        "trace": current_trace + [trace_entry],
    }

def generate_report_node(state: GraphState) -> dict[str, Any]:
    """LangGraph 节点：生成最终诊断报告。

    输入：
    - state["user_input"]: 原始日志
    - state["parsed_result"]: 日志结构化结果
    - state["rag_result"]: 知识库检索结果
    - state["memory_result"]: 历史案例搜索结果

    输出：
    - report_result: 最终报告结果
    - is_finished: 标记流程进入完成状态
    - trace: 追加一条执行记录
    """

    llm = OpenAICompatibleLLM.from_env()
    if llm is None:
        llm = FakeLLM()

    report_tool = ReportTool(llm=llm)

    report_input = {
        "raw_log": state.get("user_input", ""),
        "parsed_result": state.get("parsed_result", {}),
        "rag_result": state.get("rag_result", {}),
        "memory_result": state.get("memory_result", {}),
    }

    report_result = report_tool.run(report_input)

    trace_entry= {
        "thought": "已经生成了诊断报告，准备返回给用户。",
        "action": "report_tool",
        "action_input": report_input,
        "observation": report_result,
    }

    current_trace = state.get("trace", [])

    return {
        "report_result": report_result,
        "is_finished": True,
        "trace": current_trace + [trace_entry],
        "report_llm_source": "openai_compatible" if isinstance(llm, OpenAICompatibleLLM) else "fake",
    }

def persist_case_node(state: GraphState) -> dict[str, Any]:
    """LangGraph 节点：写入历史案例库。

    输入：
    - state["parsed_result"]: 日志结构化结果
    - state["report_result"]: 最终诊断报告结果

    输出：
    - memory_write_result: 写入 SQLite 后的回执结果
    - trace: 追加一条执行记录
    """
    parsed_result = state.get("parsed_result", {})
    report_result = state.get("report_result", {})

    memory_store = SQLiteMemory(DB_PATH)
    memory_tool = MemoryTool(memory_store=memory_store)

    memory_input = {
        "action": "add_case",
        "raw_log_summary": parsed_result.get("log_summary", ""),
        "extracted_fields": parsed_result.get("extracted_fields", {}),
        "diagnosis_summary": report_result.get("diagnosis_summary", ""),
        "root_causes": report_result.get("root_causes", []),
        "troubleshooting_steps": report_result.get("troubleshooting_steps", []),
    }

    memory_write_result = memory_tool.run(memory_input)

    trace_entry = {
        "thought": "本次诊断已经完成，将结果写入历史案例库，供后续相似问题召回。",
        "action": "memory_tool",
        "action_input": memory_input,
        "observation": memory_write_result,
    }

    current_trace = state.get("trace", [])

    return {
        "memory_write_result": memory_write_result,
        "trace": current_trace + [trace_entry],
    }
