from parser.log_parser import parse_log


def test_parse_log_extracts_fields() -> None:
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
