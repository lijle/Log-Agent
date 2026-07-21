from tools.tempo_query_tool import TempoQueryTool


def test_query_real_trace_from_tempo() -> None:
    """验证能够查询并整理刚才生成的真实 Trace。"""
    trace_id = (
        "0c8adc228ee2c069da7268eb64b58a46"
    )

    tool = TempoQueryTool()

    result = tool.run(
        {
            "trace_id": trace_id,
        }
    )

    print("\n========== Tempo 查询结果 ==========")
    print("查询成功：", result["success"])
    print("错误信息：", result["error"])
    print("Span 数量：", result["total_spans"])
    print("服务列表：", result["service_names"])

    print("\n========== Trace Timeline ==========")
    print(result["timeline_text"])

    print("\n========== Error Spans ==========")

    for error_span in result["error_spans"]:
        print(
            error_span["service_name"],
            "|",
            error_span["operation_name"],
            "|",
            error_span["status"],
        )

    assert result["success"] is True
    assert result["total_spans"] == 3

    assert set(result["service_names"]) == {
        "shp-service",
        "papi-service",
    }

    assert len(result["error_spans"]) >= 1

    database_spans = []

    for span in result["spans"]:
        attributes = span.get(
            "attributes",
            {},
        )

        if attributes.get("db.system") == "mysql":
            database_spans.append(span)

    assert len(database_spans) == 1

    database_span = database_spans[0]

    assert database_span["status"] == "ERROR"
    assert (
        database_span["operation_name"]
        == "SELECT transfer_account"
    )
    assert database_span["kind"] == "CLIENT"
    timeline = result["timeline"]

    assert "POST /transfer" in timeline[0]
    assert "POST /payment" in timeline[1]
    assert "SELECT transfer_account" in timeline[2]

    for span in result["spans"]:
        assert "=" not in span["span_id"]
        assert len(span["span_id"]) == 16