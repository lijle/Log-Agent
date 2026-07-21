import pytest

from tools.logql_query_builder import (
    build_logql_query,
    escape_logql_value,
)
from tools.logql_query_builder import (
    build_logql_query,
    build_trace_logql_query,
    escape_logql_value,
)

def test_build_query_with_service_name_only() -> None:
    """只提供服务名时，应生成标签查询。"""
    query = build_logql_query(
        service_name="mock-transfer-api",
    )

    assert query == '{service_name="mock-transfer-api"}'


def test_build_query_with_all_conditions() -> None:
    """提供完整条件时，应生成标签和正文组合查询。"""
    query = build_logql_query(
        service_name="mock-transfer-api",
        level="ERROR",
        trace_id="trc-demo-002",
        keyword="SQLTransientConnectionException",
    )

    expected_query = (
        '{service_name="mock-transfer-api", level="ERROR"} '
        '|= "trc-demo-002" '
        '|= "SQLTransientConnectionException"'
    )

    assert query == expected_query


def test_empty_service_name_should_raise_error() -> None:
    """服务名为空时，应拒绝构造无限范围查询。"""
    with pytest.raises(ValueError):
        build_logql_query(service_name="")


def test_escape_double_quote() -> None:
    """用户输入中的双引号应该被转义。"""
    escaped_value = escape_logql_value(
        'payment "failed"'
    )

    assert escaped_value == 'payment \\"failed\\"'



def test_build_trace_logql_query() -> None:
    """应该根据 Trace ID 构造跨服务查询。"""
    query = build_trace_logql_query(
        trace_id="trc-agent-001",
    )

    expected_query = (
        '{job="log-diagnosis-agent"} '
        '|= "trc-agent-001"'
    )

    assert query == expected_query


def test_empty_trace_id_should_raise_error() -> None:
    """Trace ID 为空时应该拒绝构造查询。"""
    with pytest.raises(ValueError):
        build_trace_logql_query(
            trace_id="",
        )