from __future__ import annotations

from typing import Any

from agent.agent_state import AgentState
from agent.base_agent import BaseAgent


class ReActAgent(BaseAgent):
    def run(self, user_input: str) -> dict[str, Any]:
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
        tool = self.tool_registry.get_tool(action)
        observation = tool.run(action_input)
        state.add_step(thought, action, action_input, observation)
        return observation

    @staticmethod
    def _build_rag_query(parsed_result: dict[str, Any]) -> str:
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
        fields = parsed_result.get("extracted_fields", {})
        parts = [
            fields.get("service_name", ""),
            fields.get("exception_type", ""),
            fields.get("error_message", ""),
            parsed_result.get("log_summary", ""),
        ]
        return " ".join(part for part in parts if part)
