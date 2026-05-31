"""Streamlit 应用入口。

这个文件负责把 Agent、工具、SQLite 记忆库和前端页面串起来。
你阅读这个文件时，可以把它理解为“把后端能力装配成一个可交互 UI”的地方。
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


PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "db" / "diagnosis_history.db"
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "data" / "knowledge_base"


def build_agent() -> ReActAgent:
    """构建并返回应用使用的 Agent 实例。

    作用：
    - 加载环境变量
    - 初始化 SQLite 记忆库
    - 根据环境变量选择真实 LLM 或 FakeLLM
    - 注册日志解析、RAG、Memory、报告生成等工具

    输入：
    - 无

    输出：
    - ReActAgent：已经完成依赖装配的 Agent，可直接执行 `run`
    """

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
    """从 MemoryTool 读取最近的诊断案例。

    作用：
    - 供左侧边栏展示“历史诊断”
    - 让用户快速回看最近分析过的问题

    输入：
    - agent：已经构建好的 Agent，内部要能拿到 `memory_tool`

    输出：
    - list[dict[str, Any]]：案例列表，每项包含 case_id、created_at、diagnosis_summary 等字段
    """

    memory_tool = agent.tool_registry.get_tool("memory_tool")
    result = memory_tool.run({"action": "list_recent_cases", "limit": 5})
    return result.get("cases", [])


def get_log_input(uploaded_file: Any, pasted_log: str) -> str:
    """统一整理用户输入的日志文本。

    作用：
    - 优先读取上传文件中的日志内容
    - 如果没有上传文件，则使用文本框里粘贴的日志

    输入：
    - uploaded_file：Streamlit 上传的文件对象，可能为 None
    - pasted_log：用户在文本框中输入的原始日志

    输出：
    - str：最终交给 Agent 分析的日志文本
    """

    if uploaded_file is not None:
        return uploaded_file.read().decode("utf-8", errors="ignore")
    return pasted_log.strip()


def get_document_title(doc: dict[str, Any]) -> str:
    """从知识片段中提取可展示的标题。

    作用：
    - 优先读取 Markdown 一级标题
    - 如果没有标题，则回退到源文件名

    输入：
    - doc：RAG 检索返回的文档片段，通常包含 source 和 content

    输出：
    - str：适合在 UI 中展示的知识标题
    """

    content = str(doc.get("content", "")).strip()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return str(doc.get("source", "未命名知识文档"))


def format_case_time(created_at: str) -> str:
    """把数据库中的 ISO 时间格式化为更易读的展示形式。

    作用：
    - 仅做前端展示处理
    - 让时间字符串从 `2026-05-31T10:00:00+00:00` 变得更直观

    输入：
    - created_at：SQLite 中保存的 ISO 时间字符串

    输出：
    - str：替换掉 `T` 之后的可读时间字符串
    """

    return created_at.replace("T", " ")


def main() -> None:
    """启动 Streamlit 页面并处理整条交互流程。

    作用：
    - 渲染日志输入区、样例区、历史案例区
    - 在用户点击“开始分析”后触发 Agent
    - 展示解析字段、知识检索结果、历史案例和最终报告

    输入：
    - 无。用户输入由 Streamlit 组件提供

    输出：
    - 无。结果直接渲染到 Web 页面
    """

    st.set_page_config(page_title="日志诊断 Agent", page_icon="🩺", layout="wide")
    st.title("日志诊断 Agent")
    st.caption("一个本地可运行的后端日志诊断 Agent MVP，适合学习 Agent、RAG 和排障流程。")

    agent = build_agent()

    with st.sidebar:
        st.subheader("历史诊断")
        recent_cases = load_recent_cases(agent)
        if recent_cases:
            for case in recent_cases:
                st.markdown(f"**{case['case_id']}**")
                st.caption(format_case_time(case["created_at"]))
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
