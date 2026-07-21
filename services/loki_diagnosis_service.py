from __future__ import annotations

from typing import Any

from agent.langgraph_agent import LangGraphAgent

from tools.loki_query_tool import LokiQueryTool
from tools.logql_query_builder import (
    build_logql_query,
    build_trace_logql_query,
)

class LokiDiagnosisService:
    """组织“查询 Loki + 调用 Agent 诊断”的完整业务流程。

    这个类不负责：
    - 展示页面
    - 解析日志
    - 生成报告

    这个类只负责：
    - 接收查询条件
    - 构造 LogQL
    - 调用 LokiQueryTool
    - 把日志交给 LangGraphAgent
    - 组合最终结果
    """
    def __init__(
        self,
        loki_tool: LokiQueryTool | None = None,
        agent: LangGraphAgent | None = None,
    ) -> None:
        """初始化 Loki 诊断服务。

        输入：
        - loki_tool: 可选的 Loki 工具实例
        - agent: 可选的 LangGraph Agent 实例

        输出：
        - None
        """
        if loki_tool is None:
            loki_tool = LokiQueryTool()

        if agent is None:
            agent = LangGraphAgent()

        self.loki_tool = loki_tool
        self.agent = agent

    def diagnose(
        self,
        service_name: str,
        level: str = "",
        trace_id: str = "",
        keyword: str = "",
        lookback_minutes: int = 60,
        limit: int = 100,
    ) -> dict[str, Any]:
        """从 Loki 查询日志并执行诊断。

        输入：
        - service_name: 服务名称
        - level: 日志级别
        - trace_id: Trace ID
        - keyword: 错误关键字
        - lookback_minutes: 查询最近多少分钟
        - limit: 最大日志数量

        输出：
        - success: 整体流程是否成功
        - error: 失败原因
        - logql_query: 实际执行的 LogQL
        - loki_result: Loki 查询结果
        - diagnosis_result: Agent 诊断结果
        """
        try:
            logql_query = build_logql_query(
                service_name=service_name,
                level=level,
                trace_id=trace_id,
                keyword=keyword,
            )
        except ValueError as error:
            return self._build_failure_result(
                error=str(error),
            )

        loki_result = self.loki_tool.run(
            {
                "query": logql_query,
                "lookback_minutes": lookback_minutes,
                "limit": limit,
            }
        )

        if not loki_result.get("success"):
            return self._build_failure_result(
                error=loki_result.get(
                    "error",
                    "Loki 查询失败。",
                ),
                logql_query=logql_query,
                loki_result=loki_result,
            )

        if loki_result.get("total", 0) == 0:
            return self._build_failure_result(
                error="指定条件和时间范围内没有查询到日志。",
                logql_query=logql_query,
                loki_result=loki_result,
            )

        raw_logs = loki_result.get("raw_logs", "")

        diagnosis_result = self.agent.run(raw_logs)

        return {
            "success": True,
            "error": "",
            "logql_query": logql_query,
            "loki_result": loki_result,
            "diagnosis_result": diagnosis_result,
        }



    def diagnose_by_trace(
        self,
        trace_id: str,
        lookback_minutes: int = 60,
        limit: int = 200,
    ) -> dict[str, Any]:
        """根据 Trace ID 查询跨服务日志并执行诊断。

        输入：
        - trace_id: 一次分布式请求的 Trace ID
        - lookback_minutes: 向前查询多少分钟
        - limit: 最大日志数量

        输出：
        - success: 是否成功
        - logql_query: 实际执行的跨服务 LogQL
        - service_names: 从 Loki 标签中发现的服务
        - loki_result: Loki 查询结果
        - diagnosis_result: Agent 诊断结果
        """
        try:
            logql_query = build_trace_logql_query(
                trace_id=trace_id,
            )
        except ValueError as error:
            return self._build_failure_result(
                error=str(error),
            )

        loki_result = self.loki_tool.run(
            {
                "query": logql_query,
                "lookback_minutes": lookback_minutes,
                "limit": limit,
            }
        )

        if not loki_result.get("success"):
            return self._build_failure_result(
                error=loki_result.get(
                    "error",
                    "Loki 查询失败。",
                ),
                logql_query=logql_query,
                loki_result=loki_result,
            )

        if loki_result.get("total", 0) == 0:
            return self._build_failure_result(
                error="该 Trace ID 在指定时间范围内没有相关日志。",
                logql_query=logql_query,
                loki_result=loki_result,
            )

        logs = loki_result.get("logs", [])

        service_names = self._extract_service_names(
            logs=logs,
        )

        raw_logs = loki_result.get(
            "raw_logs",
            "",
        )

        diagnosis_result = self.agent.run(
            raw_logs,
        )

        return {
            "success": True,
            "error": "",
            "logql_query": logql_query,
            "service_names": service_names,
            "loki_result": loki_result,
            "diagnosis_result": diagnosis_result,
        }

    def _build_failure_result(
        self,
        error: str,
        logql_query: str = "",
        loki_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构造统一的流程失败结果。"""
        if loki_result is None:
            loki_result = {}

        return {
            "success": False,
            "error": error,
            "logql_query": logql_query,
            "service_names": [],
            "loki_result": loki_result,
            "diagnosis_result": {},
        }

    def _extract_service_names(
        self,
        logs: list[dict[str, Any]],
    ) -> list[str]:
        """从 Loki 日志标签中提取服务名称并去重。"""
        service_names: list[str] = []

        for log_item in logs:
            labels = log_item.get(
                "labels",
                {},
            )

            service_name = str(
                labels.get("service_name", "")
            ).strip()

            if not service_name:
                continue

            if service_name in service_names:
                continue

            service_names.append(service_name)

        return service_names