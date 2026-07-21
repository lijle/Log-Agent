from services.loki_diagnosis_service import LokiDiagnosisService


def test_loki_diagnosis_service() -> None:
    """验证 Loki 诊断业务服务。"""
    service = LokiDiagnosisService()

    result = service.diagnose(
        service_name="mock-transfer-api",
        level="error",
        trace_id="trc-agent-001",
        lookback_minutes=1440,
        limit=20,
    )

    print("执行成功：", result["success"])
    print("错误信息：", result["error"])
    print("LogQL：", result["logql_query"])

    assert result["success"] is True

    diagnosis_result = result["diagnosis_result"]
    report_markdown = diagnosis_result.get(
        "report_markdown",
        "",
    )

    assert report_markdown

    print(report_markdown)