from typing import Any

from agent.langgraph_agent import LangGraphAgent
from services.loki_diagnosis_service import LokiDiagnosisService
from tools.loki_query_tool import LokiQueryTool


class FakeLokiQueryTool(LokiQueryTool):
    """模拟 Loki，不发送真实 HTTP 请求。"""

    def __init__(self) -> None:
        """不调用父类初始化，只记录收到的参数。"""
        self.received_input: dict[str, Any] = {}

    def run(
        self,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        """返回预先准备好的 SHP 和 PAPI 日志。"""
        self.received_input = input

        raw_logs = (
            "2026-07-16 10:00:00,001 INFO "
            "service=shp-service trace_id=trace-001 "
            'message="received request"\n'
            "2026-07-16 10:00:00,020 INFO "
            "service=papi-service trace_id=trace-001 "
            'message="received downstream request"\n'
            "2026-07-16 10:00:30,021 ERROR "
            "service=papi-service trace_id=trace-001 "
            "exception=ReadTimeoutException "
            'message="database request timed out"'
        )

        return {
            "success": True,
            "query": input.get("query", ""),
            "request_url": "fake://loki",
            "logs": [
                {
                    "timestamp_ns": "1001",
                    "line": "SHP received request",
                    "labels": {
                        "service_name": "shp-service",
                        "level": "INFO",
                    },
                },
                {
                    "timestamp_ns": "1002",
                    "line": "PAPI received request",
                    "labels": {
                        "service_name": "papi-service",
                        "level": "INFO",
                    },
                },
                {
                    "timestamp_ns": "1003",
                    "line": "PAPI database timeout",
                    "labels": {
                        "service_name": "papi-service",
                        "level": "ERROR",
                    },
                },
            ],
            "raw_logs": raw_logs,
            "total": 3,
            "error": "",
        }


class FakeLangGraphAgent(LangGraphAgent):
    """模拟 Agent，不调用 LLM、RAG 和数据库。"""

    def __init__(self) -> None:
        """不构建真实 LangGraph，只记录收到的日志。"""
        self.received_user_input = ""

    def run(
        self,
        user_input: str,
    ) -> dict[str, Any]:
        """记录 Service 传来的日志并返回模拟报告。"""
        self.received_user_input = user_input

        return {
            "report_markdown": (
                "## 模拟诊断报告\n"
                "PAPI 服务发生数据库请求超时。"
            ),
            "trace": [],
        }


def test_diagnose_by_trace_should_collect_services() -> None:
    """验证 Trace 诊断能发现多个服务并调用 Agent。"""
    fake_loki_tool = FakeLokiQueryTool()
    fake_agent = FakeLangGraphAgent()

    service = LokiDiagnosisService(
        loki_tool=fake_loki_tool,
        agent=fake_agent,
    )

    result = service.diagnose_by_trace(
        trace_id="trace-001",
        lookback_minutes=30,
        limit=50,
    )

    print("\n实际 LogQL：")
    print(result["logql_query"])

    print("\n发现的服务：")
    print(result["service_names"])

    print("\n交给 Agent 的日志：")
    print(fake_agent.received_user_input)

    assert result["success"] is True

    assert result["logql_query"] == (
        '{job="log-diagnosis-agent"} '
        '|= "trace-001"'
    )

    assert result["service_names"] == [
        "shp-service",
        "papi-service",
    ]

    assert fake_loki_tool.received_input == {
        "query": (
            '{job="log-diagnosis-agent"} '
            '|= "trace-001"'
        ),
        "lookback_minutes": 30,
        "limit": 50,
    }

    assert "service=shp-service" in (
        fake_agent.received_user_input
    )

    assert "service=papi-service" in (
        fake_agent.received_user_input
    )

    assert (
        result["diagnosis_result"]["report_markdown"]
        == "## 模拟诊断报告\n"
        "PAPI 服务发生数据库请求超时。"
    )