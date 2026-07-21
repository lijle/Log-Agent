from agent.langgraph_agent import LangGraphAgent
from tools.logql_query_builder import build_logql_query
from tools.loki_query_tool import LokiQueryTool


def test_diagnose_logs_from_loki() -> None:
    """验证从 Loki 查询日志并交给 LangGraph Agent 诊断。"""

    # 第一步：将普通查询条件转换成 LogQL。
    logql_query = build_logql_query(
        service_name="mock-transfer-api",
        level="error",
        trace_id="trc-agent-001",
    )

    # 第二步：调用 Loki，获得匹配的业务日志。
    loki_tool = LokiQueryTool()

    loki_result = loki_tool.run(
        {
            "query": logql_query,
            "limit": 20,
            "lookback_minutes": 60,
        }
    )

    assert loki_result["success"] is True
    assert loki_result["total"] > 0
    assert loki_result["raw_logs"]

    print("\n========== Loki 查询 ==========")
    print("LogQL：", logql_query)
    print("日志数量：", loki_result["total"])
    print(loki_result["raw_logs"])

    # 第三步：把 Loki 返回的日志交给现有 LangGraph Agent。
    agent = LangGraphAgent()

    diagnosis_result = agent.run(
        loki_result["raw_logs"]
    )

    report_markdown = diagnosis_result.get(
        "report_markdown",
        "",
    )

    assert report_markdown

    print("\n========== 结构化字段 ==========")
    print(diagnosis_result["parsed_result"])

    print("\n========== Agent 诊断报告 ==========")
    print(report_markdown)

    print("\n========== Agent 执行信息 ==========")
    print(
        "决策来源：",
        diagnosis_result.get("decision_source"),
    )
    print(
        "报告来源：",
        diagnosis_result.get("report_llm_source"),
    )
    print(
        "轨迹长度：",
        len(diagnosis_result.get("trace", [])),
    )