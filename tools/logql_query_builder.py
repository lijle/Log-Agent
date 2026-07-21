from __future__ import annotations


def escape_logql_value(value: str) -> str:
    """转义 LogQL 字符串中的特殊字符。

    输入：
    - value: 用户输入的查询值

    输出：
    - 可以安全放入 LogQL 双引号中的字符串
    """
    escaped_value = value.replace("\\", "\\\\")
    escaped_value = escaped_value.replace('"', '\\"')

    return escaped_value

def build_logql_query(
    service_name: str,
    level: str = "",
    trace_id: str = "",
    keyword: str = "",
) -> str:
    """根据常见日志查询条件构造 LogQL。

    输入：
    - service_name: 服务名称，必填
    - level: 日志等级，可选
    - trace_id: 链路追踪 ID，可选
    - keyword: 异常类型或错误关键字，可选

    输出：
    - 一条合法的 LogQL 查询语句

    异常：
    - service_name 为空时抛出 ValueError
    """
    service_name = service_name.strip()
    level = level.strip().upper()
    trace_id = trace_id.strip()
    keyword = keyword.strip()

    if not service_name:
        raise ValueError("service_name 不能为空。")

    label_conditions: list[str] = []

    escaped_service_name = escape_logql_value(service_name)
    label_conditions.append(
        f'service_name="{escaped_service_name}"'
    )

    if level:
        escaped_level = escape_logql_value(level)
        label_conditions.append(
            f'level="{escaped_level}"'
        )

    label_selector = "{" + ", ".join(label_conditions) + "}"

    content_filters: list[str] = []

    if trace_id:
        escaped_trace_id = escape_logql_value(trace_id)
        content_filters.append(
            f'|= "{escaped_trace_id}"'
        )

    if keyword:
        escaped_keyword = escape_logql_value(keyword)
        content_filters.append(
            f'|= "{escaped_keyword}"'
        )

    query_parts = [label_selector]
    query_parts.extend(content_filters)

    return " ".join(query_parts)

def build_trace_logql_query(
    trace_id: str,
    job: str = "log-diagnosis-agent",
) -> str:
    """构造跨服务 Trace 日志查询。

    输入：
    - trace_id: 需要调查的 Trace ID
    - job: Loki 日志采集任务名称

    输出：
    - 查询该 Trace 全部相关日志的 LogQL
    """
    trace_id = trace_id.strip()
    job = job.strip()

    if not trace_id:
        raise ValueError("trace_id 不能为空。")

    if not job:
        raise ValueError("job 不能为空。")

    escaped_trace_id = escape_logql_value(
        trace_id
    )

    escaped_job = escape_logql_value(
        job
    )

    return (
        f'{{job="{escaped_job}"}} '
        f'|= "{escaped_trace_id}"'
    )