from tools.loki_query_tool import LokiQueryTool


def test_query_logs_from_loki() -> None:
    """验证能够从本地 Loki 查询日志。"""
    tool = LokiQueryTool()

    tool_input = {
        "query": '{service_name="mock-transfer-api"}',
        "limit": 20,
        "lookback_minutes": 7 * 24 * 60,
    }

    result = tool.run(tool_input)

    print("查询成功：", result["success"])
    print("日志数量：", result["total"])
    print("错误信息：", result["error"])
    print("原始日志：")
    print(result["raw_logs"])

    assert result["success"] is True
    assert result["total"] > 0
    assert result["raw_logs"]


if __name__ == "__main__":
    test_query_logs_from_loki()