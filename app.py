"""Streamlit 应用入口。

这个文件负责把 Agent、工具、SQLite 记忆库和前端页面串起来。
如果你想快速理解整个项目怎么跑，优先看这里和 agent/react_agent.py。
"""

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

from agent.langgraph_agent import LangGraphAgent


PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "db" / "diagnosis_history.db"
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "data" / "knowledge_base"


def build_agent() -> ReActAgent:
    """构建并返回应用使用的 Agent 实例。

    流程：
    1. 加载环境变量
    2. 初始化 SQLiteMemory
    3. 根据环境变量选择真实 LLM 或 FakeLLM
    4. 注册 log_parser / rag / memory / report 工具
    5. 返回可直接执行的 ReActAgent
    """

    load_dotenv()
    memory_store = SQLiteMemory(DB_PATH)
    llm = OpenAICompatibleLLM.from_env()
    if llm is None:
        llm = FakeLLM()

    registry = ToolRegistry()
    registry.register_tool(LogParserTool())
    registry.register_tool(RAGTool(knowledge_base_dir=KNOWLEDGE_BASE_DIR, default_top_k=4))
    registry.register_tool(MemoryTool(memory_store=memory_store))
    registry.register_tool(ReportTool(llm=llm, memory_store=memory_store))

    return ReActAgent(
        name="log-diagnosis-agent",
        llm=llm,
        tool_registry=registry,
        memory=memory_store,
    )

def build_langgraph_agent() -> LangGraphAgent:
    """构建并返回 LangGraph 版本的 Agent。"""
    load_dotenv()
    return LangGraphAgent()


def load_recent_cases() -> list[dict[str, Any]]:
    """读取最近的历史案例，用于侧边栏展示。"""

    memory_store = SQLiteMemory(DB_PATH)
    memory_tool = MemoryTool(memory_store=memory_store)
    result = memory_tool.run({"action": "list_recent_cases", "limit": 5})
    return result.get("cases", [])


def get_log_input(uploaded_file: Any, pasted_log: str) -> str:
    """统一处理日志输入来源。

    优先级：
    1. 如果用户上传了文件，读取文件内容
    2. 否则使用文本框里的日志内容
    """

    if uploaded_file is not None:
        return uploaded_file.read().decode("utf-8", errors="ignore")
    return pasted_log.strip()


def get_document_title(doc: dict[str, Any]) -> str:
    """从知识片段中提取 Markdown 标题，供 UI 展示。"""

    content = str(doc.get("content", "")).strip()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return str(doc.get("source", "未命名知识文档"))


def format_case_time(created_at: str) -> str:
    """把 ISO 时间格式转成更直观的展示形式。"""

    return created_at.replace("T", " ")


def main() -> None:
    """启动 Streamlit 页面，并把 Agent 结果渲染出来。"""

    st.set_page_config(page_title="日志诊断 Agent", page_icon="🩺", layout="wide")
    st.title("日志诊断 Agent")
    st.caption("一个本地可运行的后端日志诊断 Agent MVP，适合学习 ReAct、RAG 和排障流程。")


    with st.sidebar:
        run_mode = st.radio(
            "运行模式",
            ["ReAct Agent", "LangGraph Agent"],
            index=0,
        )

        st.subheader("历史诊断")
        recent_cases = load_recent_cases()
        if recent_cases:
            for case in recent_cases:
                st.markdown(f"**{case['case_id']}**")
                st.caption(format_case_time(case["created_at"]))
                st.write(case["diagnosis_summary"])
        else:
            st.info("暂无历史案例。")


    if run_mode == "LangGraph Agent":
        agent = build_langgraph_agent()
    else:
        agent = build_agent()


    left, right = st.columns([1, 1])

    with left:
        st.subheader("输入日志")
        pasted_log = st.text_area(
            "粘贴日志内容",
            height=320,
            placeholder="在这里粘贴应用日志...",
        )
        uploaded_file = st.file_uploader("或上传 .log / .txt 文件", type=["log", "txt"])
        analyze = st.button("开始分析", type="primary", use_container_width=True)

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

        st.subheader("提取字段")
        st.json(parsed.get("extracted_fields", {}))

        st.subheader("日志摘要")
        st.write(parsed.get("log_summary", ""))

        st.subheader("检索到的知识")
        docs = rag_result.get("documents", [])
        if docs:
            for idx, doc in enumerate(docs, start=1):
                title = get_document_title(doc)
                source = doc.get("source", "unknown")
                with st.expander(f"知识片段 {idx} | {title}"):
                    st.caption(f"来源文件: {source} | 匹配分数: {doc.get('score', 0):.4f}")
                    st.write(doc.get("content", ""))
        else:
            st.info("未检索到相关知识片段。")

        st.subheader("相关历史案例")
        cases = memory_result.get("cases", [])
        if cases:
            st.dataframe(cases, use_container_width=True)
        else:
            st.info("未找到相关历史案例。")

        st.subheader("诊断报告")
        st.markdown(report)

        with st.expander("Agent 执行轨迹"):
            st.json(result.get("trace", []))

        with st.expander("完整结果 JSON"):
            st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")


if __name__ == "__main__":
    main()
