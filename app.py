from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from agent.react_agent import ReActAgent
from llm.fake_llm import FakeLLM
from llm.openai_compatible_llm import OpenAICompatibleLLM
from memory.sqlite_memory import SQLiteMemory
from tools.log_parser_tool import LogParserTool
from tools.memory_tool import MemoryTool
from tools.rag_tool import RAGTool
from tools.report_tool import ReportTool
from tools.tool_registry import ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "db" / "diagnosis_history.db"
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "data" / "knowledge_base"


def build_agent() -> ReActAgent:
    load_dotenv()
    memory_store = SQLiteMemory(DB_PATH)
    llm = OpenAICompatibleLLM.from_env()
    if llm is None:
        llm = FakeLLM()

    registry = ToolRegistry()
    registry.register_tool(LogParserTool())
    registry.register_tool(RAGTool(knowledge_base_dir=KNOWLEDGE_BASE_DIR))
    registry.register_tool(MemoryTool(memory_store=memory_store))
    registry.register_tool(ReportTool(llm=llm, memory_store=memory_store))

    return ReActAgent(
        name="log-diagnosis-agent",
        llm=llm,
        tool_registry=registry,
        memory=memory_store,
    )


def load_recent_cases(agent: ReActAgent) -> list[dict[str, Any]]:
    memory_tool = agent.tool_registry.get_tool("memory_tool")
    result = memory_tool.run({"action": "list_recent_cases", "limit": 5})
    return result.get("cases", [])


def get_log_input(uploaded_file: Any, pasted_log: str) -> str:
    if uploaded_file is not None:
        return uploaded_file.read().decode("utf-8", errors="ignore")
    return pasted_log.strip()


def main() -> None:
    st.set_page_config(page_title="Log Diagnosis Agent", page_icon="🧭", layout="wide")
    st.title("Log Diagnosis Agent")
    st.caption("本地可运行的后端日志诊断 Agent MVP")

    agent = build_agent()

    with st.sidebar:
        st.subheader("历史诊断")
        recent_cases = load_recent_cases(agent)
        if recent_cases:
            for case in recent_cases:
                st.markdown(f"**{case['case_id']}**")
                st.caption(case["created_at"])
                st.write(case["diagnosis_summary"])
        else:
            st.info("暂无历史案例。")

    left, right = st.columns([1, 1])

    with left:
        st.subheader("输入日志")
        pasted_log = st.text_area(
            "粘贴日志内容",
            height=320,
            placeholder="在这里粘贴应用日志...",
        )
        uploaded_file = st.file_uploader("或上传 .log / .txt 文件", type=["log", "txt"])
        analyze = st.button("Analyze Logs", type="primary", use_container_width=True)

    with right:
        st.subheader("内置样例")
        sample_dir = PROJECT_ROOT / "data" / "mock_logs"
        samples = sorted(sample_dir.glob("*.log"))
        for sample in samples:
            if st.button(sample.name, use_container_width=True):
                st.session_state["sample_log"] = sample.read_text(encoding="utf-8")

        if st.session_state.get("sample_log"):
            st.code(st.session_state["sample_log"], language="text")

    if analyze:
        raw_log = get_log_input(uploaded_file, pasted_log or st.session_state.get("sample_log", ""))
        if not raw_log:
            st.warning("请先粘贴日志或上传文件。")
            return

        with st.spinner("正在分析日志..."):
            result = agent.run(raw_log)

        parsed = result.get("parsed_result", {})
        rag_result = result.get("rag_result", {})
        memory_result = result.get("memory_result", {})
        report = result.get("report_markdown", "未生成报告。")

        st.subheader("Extracted Fields")
        st.json(parsed.get("extracted_fields", {}))

        st.subheader("Compact Log Summary")
        st.write(parsed.get("log_summary", ""))

        st.subheader("Retrieved Knowledge")
        docs = rag_result.get("documents", [])
        if docs:
            for idx, doc in enumerate(docs, start=1):
                with st.expander(f"Chunk {idx} | {doc.get('source', 'unknown')}"):
                    st.write(doc.get("content", ""))
                    st.caption(f"score={doc.get('score', 0):.4f}")
        else:
            st.info("未检索到相关知识片段。")

        st.subheader("Related Historical Cases")
        cases = memory_result.get("cases", [])
        if cases:
            st.dataframe(cases, use_container_width=True)
        else:
            st.info("未找到相关历史案例。")

        st.subheader("Diagnosis Report")
        st.markdown(report)

        with st.expander("Agent Trace"):
            st.json(result.get("trace", []))

        with st.expander("Full Result JSON"):
            st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")


if __name__ == "__main__":
    main()
