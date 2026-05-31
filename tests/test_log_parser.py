from parser.log_parser import parse_log


def test_parse_log_extracts_fields() -> None:
    """验证日志解析器能提取关键字段。

    作用：
    - 确认 parse_log 能正确提取时间、级别、服务名、trace_id、异常名和状态码
    - 防止后续改动破坏最基础的解析能力

    输入：
    - 无。测试内部构造固定日志样本

    输出：
    - None：断言通过则表示测试成功
    """

    raw_log = """
    2026-05-29 10:15:21,456 ERROR service=order-service trace_id=trc-9f2a status=504
    Downstream call failed: ReadTimeoutException: timeout while calling inventory-service after 3000ms
    """.strip()

    result = parse_log(raw_log)
    fields = result["extracted_fields"]

    assert fields["timestamp"] == "2026-05-29 10:15:21,456"
    assert fields["log_level"] == "ERROR"
    assert fields["service_name"] == "order-service"
    assert fields["trace_id"] == "trc-9f2a"
    assert fields["exception_type"] == "ReadTimeoutException"
    assert fields["http_status_code"] == 504
    assert "timeout" in fields["error_message"].lower()
