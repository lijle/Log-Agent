"""ReAct 风格 Agent 的主执行流程。

这个文件是整个项目最关键的调度层：
- 它决定先解析日志
- 再检索知识库
- 再搜索历史记忆
- 最后生成报告并写回记忆库
"""

from __future__ import annotations

from typing import Any

from agent.agent_state import AgentState
from agent.base_agent import BaseAgent


class ReActAgent(BaseAgent):
    """项目中的主 Agent 实现。

    作用：
    - 按 ReAct 风格记录 Thought / Action / Observation
    - 串联各个工具，完成一次完整的日志诊断
    - 把执行轨迹和最终结果一起返回给 UI
    """

    def run(self, user_input: str) -> dict[str, Any]:
        """执行一次完整的日志诊断流程。

        作用：
        - 创建本次运行的 AgentState
        - 依次调用日志解析、RAG、记忆检索、报告生成、记忆写入
        - 产出页面展示所需的所有结构化结果

        输入：
        - user_input：用户粘贴或上传的原始日志文本

        输出：
        - dict[str, Any]：包含 parsed_result、rag_result、memory_result、report_markdown、trace 等字段
        """

        state = AgentState(user_input=user_input)

        parser_input = {"raw_log": user_input}
        parsed_result = self._run_tool(
            state=state,
            thought="先解析原始日志，提取异常、服务名、请求标识和状态码等关键字段。",
            action="log_parser_tool",
            action_input=parser_input,
        )

        extracted_fields = parsed_result.get("extracted_fields", {})
        rag_query = self._build_rag_query(parsed_result)
        rag_result = self._run_tool(
            state=state,
            thought="根据日志摘要和异常字段检索本地排障知识库，补充诊断上下文。",
            action="rag_tool",
            action_input={"query": rag_query, "top_k": 4},
        )

        memory_query = self._build_memory_query(parsed_result)
        memory_result = self._run_tool(
            state=state,
            thought="搜索历史诊断案例，看看是否存在相似错误模式。",
            action="memory_tool",
            action_input={"action": "search_cases", "query": memory_query, "limit": 3},
        )

        report_result = self._run_tool(
            state=state,
            thought="综合日志证据、知识库内容和历史案例，生成结构化诊断报告。",
            action="report_tool",
            action_input={
                "raw_log": user_input,
                "parsed_result": parsed_result,
                "rag_result": rag_result,
                "memory_result": memory_result,
            },
        )

        case_payload = {
            "action": "add_case",
            "raw_log_summary": parsed_result.get("log_summary", ""),
            "extracted_fields": extracted_fields,
            "diagnosis_summary": report_result.get("diagnosis_summary", ""),
            "root_causes": report_result.get("root_causes", []),
            "troubleshooting_steps": report_result.get("troubleshooting_steps", []),
        }
        memory_write_result = self._run_tool(
            state=state,
            thought="将本次诊断结果写入历史案例库，便于后续相似问题召回。",
            action="memory_tool",
            action_input=case_payload,
        )

        result = {
            "parsed_result": parsed_result,
            "rag_result": rag_result,
            "memory_result": memory_result,
            "report_markdown": report_result.get("report_markdown", ""),
            "report_result": report_result,
            "memory_write_result": memory_write_result,
            "trace": [
                {
                    "thought": step.thought,
                    "action": step.action,
                    "action_input": step.action_input,
                    "observation": step.observation,
                }
                for step in state.steps
            ],
        }
        state.final_answer = result
        return result

    def _run_tool(
        self,
        state: AgentState,
        thought: str,
        action: str,
        action_input: dict[str, Any],
    ) -> dict[str, Any]:
        """执行单个工具，并把结果记入 AgentState。

        作用：
        - 根据工具名从 ToolRegistry 取出工具
        - 执行工具
        - 记录一条 ReAct 风格步骤，方便 UI 展示执行轨迹

        输入：
        - state：当前运行的 AgentState
        - thought：执行前的思考说明
        - action：工具名称
        - action_input：传给工具的结构化输入

        输出：
        - dict[str, Any]：工具执行后的 observation 结果
        """

        tool = self.tool_registry.get_tool(action)
        observation = tool.run(action_input)
        state.add_step(thought, action, action_input, observation)
        return observation

    @staticmethod
    def _build_rag_query(parsed_result: dict[str, Any]) -> str:
        """基于解析结果构造知识库检索语句。

        作用：
        - 把日志摘要、异常类型、错误信息、状态码拼成查询文本
        - 给本地 TF-IDF 检索器提供更完整的上下文

        输入：
        - parsed_result：日志解析工具返回的结果

        输出：
        - str：用于 RAGTool 的查询字符串
        """

        fields = parsed_result.get("extracted_fields", {})
        parts = [
            parsed_result.get("log_summary", ""),
            fields.get("exception_type", ""),
            fields.get("error_message", ""),
            str(fields.get("http_status_code", "")),
        ]
        return " ".join(part for part in parts if part)

    @staticmethod
    def _build_memory_query(parsed_result: dict[str, Any]) -> str:
        """基于解析结果构造历史案例搜索语句。

        作用：
        - 把服务名、异常名、错误信息和摘要拼接起来
        - 用于 SQLite 中的模糊匹配搜索

        输入：
        - parsed_result：日志解析工具返回的结果

        输出：
        - str：用于 MemoryTool 搜索历史案例的查询字符串
        """

        fields = parsed_result.get("extracted_fields", {})
        parts = [
            fields.get("service_name", ""),
            fields.get("exception_type", ""),
            fields.get("error_message", ""),
            parsed_result.get("log_summary", ""),
        ]
        return " ".join(part for part in parts if part)
