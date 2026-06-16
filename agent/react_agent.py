"""成熟规则兜底 + LLM 主决策的 ReAct Agent。

主流程可以概括成：
1. 初始化 AgentState
2. 每轮让 Agent 决定下一步动作
3. 执行工具并拿到 observation
4. 把 observation 写回 state
5. 证据足够时转入 report_tool
6. 诊断完成后写入 SQLite 历史案例
"""

from __future__ import annotations

from typing import Any

from agent.agent_state import AgentState
from agent.base_agent import BaseAgent
from agent.react_parser import parse_react_output
from agent.react_prompts import REACT_SYSTEM_PROMPT, build_react_user_prompt
from agent.react_schema import ReActDecision
from llm.fake_llm import FakeLLM


class ReActAgent(BaseAgent):
    """基于多轮状态驱动的日志诊断 Agent。"""

    max_iterations = 6

    def run(self, user_input: str) -> dict[str, Any]:
        """执行完整的 ReAct 诊断循环。

        输入：
        - user_input: 用户输入的原始日志

        输出：
        - dict[str, Any]: 包含解析结果、检索结果、最终报告和 trace 的完整结果
        """

        state = AgentState(user_input=user_input)

        while not state.is_finished and state.iteration_count < self.max_iterations:
            state.iteration_count += 1
            thought, action, action_input = self._decide_next_step(state)

            observation = self._run_tool(
                state=state,
                thought=thought,
                action=action,
                action_input=action_input,
            )
            self._update_state_from_observation(state, action, observation)

            if action == "report_tool":
                break

        if state.report_result:
            memory_write_result = self._run_tool(
                state=state,
                thought="本次诊断已经完成，写入历史案例库，方便后续相似问题召回。",
                action="memory_tool",
                action_input={
                    "action": "add_case",
                    "raw_log_summary": state.parsed_result.get("log_summary", ""),
                    "extracted_fields": state.parsed_result.get("extracted_fields", {}),
                    "diagnosis_summary": state.report_result.get("diagnosis_summary", ""),
                    "root_causes": state.report_result.get("root_causes", []),
                    "troubleshooting_steps": state.report_result.get("troubleshooting_steps", []),
                },
            )
            state.memory_write_result = memory_write_result

        result = self._build_final_result(state)
        state.final_answer = result
        return result

    def _run_tool(
        self,
        state: AgentState,
        thought: str,
        action: str,
        action_input: dict[str, Any],
    ) -> dict[str, Any]:
        """执行工具，并把这一轮 Thought/Action/Observation 记入 trace。"""

        tool = self.tool_registry.get_tool(action)
        observation = tool.run(action_input)
        state.add_step(thought, action, action_input, observation)
        return observation

    def _decide_next_step(self, state: AgentState) -> tuple[str, str, dict[str, Any]]:
        """统一下一步决策入口。

        决策顺序：
        1. 优先尝试 LLM 决策
        2. 如果 LLM 不可用、输出不合法、或解析失败，则回退到规则版
        """

        llm_decision = self._decide_next_step_with_llm(state)
        if llm_decision is not None:
            state.last_decision_source = "llm"
            if llm_decision.is_final:
                return (
                    llm_decision.thought,
                    "report_tool",
                    self._build_report_input(state),
                )
            return (
                llm_decision.thought,
                llm_decision.action or "report_tool",
                llm_decision.action_input,
            )

        state.last_decision_source = "rule"
        return self._decide_next_step_with_rules(state)

    def _decide_next_step_with_llm(self, state: AgentState) -> ReActDecision | None:
        """让真实 LLM 决定下一步动作；FakeLLM 时直接回退规则版。"""

        if isinstance(self.llm, FakeLLM):
            return None

        state_summary = self._build_state_summary(state)
        tools_text = "\n".join(
            [
                "- log_parser_tool: Parse raw application logs and extract structured error fields.",
                "- rag_tool: Retrieve relevant troubleshooting knowledge from local markdown documents.",
                '- memory_tool: Search historical diagnosis cases in SQLite using {"action": "search_cases", "query": "...", "limit": 3}.',
            ]
        )

        user_prompt = build_react_user_prompt(
            user_input=state.user_input,
            state_summary=state_summary,
            tools_text=tools_text,
        )

        try:
            raw_output = self.llm.generate(
                system_prompt=REACT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            decision = parse_react_output(raw_output)
            if self._is_valid_decision(decision):
                return decision
            return None
        except Exception:
            return None

    def _decide_next_step_with_rules(self, state: AgentState) -> tuple[str, str, dict[str, Any]]:
        """规则版下一步决策器。

        它是 LLM 决策失败时的兜底方案，也是理解 Agent 主流程最直观的地方。
        """

        if not state.parsed_result:
            return (
                "当前还没有结构化日志结果，先解析原始日志，提取关键字段。",
                "log_parser_tool",
                {"raw_log": state.user_input},
            )

        fields = state.parsed_result.get("extracted_fields", {})

        if not state.rag_result and self._is_ready_for_search(state):
            return (
                "已经拿到异常类型、错误信息或日志摘要等线索，先检索知识库补充背景知识。",
                "rag_tool",
                {
                    "query": self._build_rag_query(state.parsed_result),
                    "top_k": 4,
                },
            )

        if not state.memory_result and (fields.get("service_name") or fields.get("exception_type")):
            return (
                "当前已经知道服务名或异常类型，继续搜索历史案例，看看是否有相似问题。",
                "memory_tool",
                {
                    "action": "search_cases",
                    "query": self._build_memory_query(state.parsed_result),
                    "limit": 3,
                },
            )

        if self._is_ready_to_answer(state):
            return (
                "当前结构化字段、知识检索结果和历史案例已经足够，进入最终报告生成。",
                "report_tool",
                self._build_report_input(state),
            )

        return (
            "虽然证据仍不完整，但当前可用工具已基本尝试完，生成一份带证据不足提示的诊断报告。",
            "report_tool",
            self._build_report_input(state),
        )

    def _update_state_from_observation(
        self,
        state: AgentState,
        action: str,
        observation: dict[str, Any],
    ) -> None:
        """根据 observation 更新 AgentState。

        你可以把它理解成：把这一轮新拿到的证据写回 Agent 的工作记忆。
        """

        if action == "log_parser_tool":
            state.parsed_result = observation
            state.missing_evidence = self._collect_missing_evidence(state)
            return

        if action == "rag_tool":
            state.rag_result = observation
            state.missing_evidence = self._collect_missing_evidence(state)
            return

        if action == "memory_tool":
            tool_action = ""
            if state.steps:
                tool_action = state.steps[-1].action_input.get("action", "")

            if tool_action == "search_cases":
                state.memory_result = observation
            elif tool_action == "add_case":
                state.memory_write_result = observation

            state.missing_evidence = self._collect_missing_evidence(state)
            return

        if action == "report_tool":
            state.report_result = observation
            state.missing_evidence = self._collect_missing_evidence(state)
            state.final_answer = observation
            state.is_finished = True

    def _build_report_input(self, state: AgentState) -> dict[str, Any]:
        """构造 report_tool 输入。"""

        return {
            "raw_log": state.user_input,
            "parsed_result": state.parsed_result,
            "rag_result": state.rag_result,
            "memory_result": state.memory_result,
        }

    def _build_final_result(self, state: AgentState) -> dict[str, Any]:
        """组装最终返回结果。

        输出是给 Streamlit UI 直接消费的完整结构。
        """

        return {
            "parsed_result": state.parsed_result,
            "rag_result": state.rag_result,
            "memory_result": state.memory_result,
            "report_markdown": state.report_result.get("report_markdown", ""),
            "report_result": state.report_result,
            "memory_write_result": state.memory_write_result,
            "missing_evidence": state.missing_evidence,
            "decision_source": state.last_decision_source,
            "iteration_count": state.iteration_count,
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

    def _build_state_summary(self, state: AgentState) -> dict[str, Any]:
        """把当前 AgentState 整理成适合给 LLM 阅读的摘要。"""

        return {
            "iteration_count": state.iteration_count,
            "parsed_result": state.parsed_result,
            "rag_result_summary": {
                "query": state.rag_result.get("query"),
                "document_count": len(state.rag_result.get("documents", [])),
            },
            "memory_result_summary": {
                "case_count": len(state.memory_result.get("cases", [])),
            },
            "missing_evidence": self._collect_missing_evidence(state),
            "executed_steps": [
                {
                    "action": step.action,
                    "action_input": step.action_input,
                }
                for step in state.steps
            ],
        }

    def _is_valid_decision(self, decision: ReActDecision) -> bool:
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

    def _is_ready_to_answer(self, state: AgentState) -> bool:
        """判断当前证据是否足够进入最终报告阶段。"""

        parsed = state.parsed_result.get("extracted_fields", {})
        if not parsed:
            return False

        # 这三个字段最能回答：
        # 1. 谁出问题了
        # 2. 属于什么类型的问题
        # 3. 具体怎么坏的
        core_fields = [
            parsed.get("service_name"),
            parsed.get("exception_type"),
            parsed.get("error_message"),
        ]
        core_score = sum(1 for item in core_fields if item)
        has_knowledge = bool(state.rag_result.get("documents"))
        has_history = bool(state.memory_result.get("cases"))
        return core_score >= 2 and (has_knowledge or has_history)

    def _is_ready_for_search(self, state: AgentState) -> bool:
        """判断当前是否具备发起检索的基本条件。"""

        fields = state.parsed_result.get("extracted_fields", {})
        return any(
            [
                fields.get("exception_type"),
                fields.get("error_message"),
                fields.get("service_name"),
                fields.get("http_status_code"),
                state.parsed_result.get("log_summary"),
            ]
        )

    def _collect_missing_evidence(self, state: AgentState) -> list[str]:
        """汇总当前仍然缺失的关键证据。"""

        missing: list[str] = []
        fields = state.parsed_result.get("extracted_fields", {})

        if not fields.get("service_name"):
            missing.append("service_name")
        if not fields.get("exception_type"):
            missing.append("exception_type")
        if not fields.get("error_message"):
            missing.append("error_message")
        if not state.rag_result.get("documents"):
            missing.append("knowledge")
        if not state.memory_result.get("cases"):
            missing.append("history")

        return missing

    @staticmethod
    def _build_rag_query(parsed_result: dict[str, Any]) -> str:
        """基于解析结果构造知识库检索语句。

        输入来源：
        - log_summary: 给检索一个整体概览
        - exception_type: 给检索最稳定的故障类别信号
        - error_message: 给检索更细粒度的错误细节
        - http_status_code: 给检索额外的结果状态提示
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
        """基于解析结果构造历史案例搜索语句。"""

        fields = parsed_result.get("extracted_fields", {})
        parts = [
            fields.get("service_name", ""),
            fields.get("exception_type", ""),
            fields.get("error_message", ""),
            parsed_result.get("log_summary", ""),
        ]
        return " ".join(part for part in parts if part)
