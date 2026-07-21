from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_LOG_DIR = PROJECT_ROOT / "runtime_logs"

OTLP_HTTP_ENDPOINT = "http://localhost:4318/v1/traces"


def create_tracer_provider(
    service_name: str,
) -> TracerProvider:
    """为一个模拟服务创建 OpenTelemetry TracerProvider。"""
    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": "local",
        }
    )

    provider = TracerProvider(
        resource=resource,
    )

    exporter = OTLPSpanExporter(
        endpoint=OTLP_HTTP_ENDPOINT,
    )

    processor = BatchSpanProcessor(
        exporter,
    )

    provider.add_span_processor(
        processor,
    )

    return provider


def format_trace_id(trace_id: int) -> str:
    """将整数 Trace ID 转换成固定32位十六进制字符串。"""
    return format(trace_id, "032x")


def format_span_id(span_id: int) -> str:
    """将整数 Span ID 转换成固定16位十六进制字符串。"""
    return format(span_id, "016x")


def format_log_time(log_time: datetime) -> str:
    """将时间转换成项目日志使用的格式。"""
    return log_time.strftime(
        "%Y-%m-%d %H:%M:%S,%f"
    )[:-3]


def write_correlated_logs(
    trace_id: str,
    shp_span_id: str,
    papi_span_id: str,
) -> Path:
    """生成与 Tempo Trace 使用相同 ID 的模拟业务日志。"""
    start_time = datetime.now()
    request_id = f"req-{uuid4().hex[:8]}"

    log_lines = [
        (
            f"{format_log_time(start_time)} INFO "
            f"service=shp-service "
            f"trace_id={trace_id} "
            f"span_id={shp_span_id} "
            f"request_id={request_id} "
            'status=200 message="received transfer request"'
        ),
        (
            f"{format_log_time(start_time + timedelta(milliseconds=20))} "
            f"INFO service=papi-service "
            f"trace_id={trace_id} "
            f"span_id={papi_span_id} "
            f"parent_span_id={shp_span_id} "
            f"request_id={request_id} "
            'status=200 message="received request from shp-service"'
        ),
        (
            f"{format_log_time(start_time + timedelta(seconds=30))} "
            f"ERROR service=papi-service "
            f"trace_id={trace_id} "
            f"span_id={papi_span_id} "
            f"parent_span_id={shp_span_id} "
            f"request_id={request_id} "
            f"status=504 exception=ReadTimeoutException "
            'message="database request timed out after 30000ms"'
        ),
        (
            f"{format_log_time(start_time + timedelta(seconds=30, milliseconds=10))} "
            f"ERROR service=shp-service "
            f"trace_id={trace_id} "
            f"span_id={shp_span_id} "
            f"request_id={request_id} "
            f"status=500 exception=DownstreamServiceException "
            'message="papi-service request failed"'
        ),
    ]

    RUNTIME_LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_file = (
        RUNTIME_LOG_DIR
        / f"otel_trace_{trace_id[:12]}.log"
    )

    # 最后的换行符用于通知 Promtail：最后一行已经完整结束。
    log_file.write_text(
        "\n".join(log_lines) + "\n",
        encoding="utf-8",
    )

    return log_file


def generate_trace() -> None:
    """生成 SHP -> PAPI -> database 的跨服务 Trace。"""
    shp_provider = create_tracer_provider(
        "shp-service"
    )
    papi_provider = create_tracer_provider(
        "papi-service"
    )

    shp_tracer = shp_provider.get_tracer(
        "shp-service"
    )
    papi_tracer = papi_provider.get_tracer(
        "papi-service"
    )

    with shp_tracer.start_as_current_span(
        "POST /transfer",
        kind=SpanKind.SERVER,
    ) as shp_span:
        shp_span.set_attribute(
            "http.request.method",
            "POST",
        )
        shp_span.set_attribute(
            "http.route",
            "/transfer",
        )

        trace_id = format_trace_id(
            shp_span.get_span_context().trace_id
        )
        shp_span_id = format_span_id(
            shp_span.get_span_context().span_id
        )

        with papi_tracer.start_as_current_span(
            "POST /payment",
            kind=SpanKind.SERVER,
        ) as papi_span:
            papi_span.set_attribute(
                "peer.service",
                "shp-service",
            )

            papi_span_id = format_span_id(
                papi_span.get_span_context().span_id
            )

            with papi_tracer.start_as_current_span(
                "SELECT transfer_account",
                kind=SpanKind.CLIENT,
            ) as database_span:
                database_span.set_attribute(
                    "db.system",
                    "mysql",
                )
                database_span.set_attribute(
                    "db.operation.name",
                    "SELECT",
                )
                database_span.set_attribute(
                    "server.address",
                    "mock-db",
                )
                database_span.set_attribute(
                    "timeout.ms",
                    30000,
                )

                timeout_error = TimeoutError(
                    "database request timed out after 30000ms"
                )

                database_span.record_exception(
                    timeout_error
                )
                database_span.set_status(
                    Status(
                        StatusCode.ERROR,
                        str(timeout_error),
                    )
                )

            papi_span.set_status(
                Status(
                    StatusCode.ERROR,
                    "database request timed out",
                )
            )

        shp_span.set_status(
            Status(
                StatusCode.ERROR,
                "papi-service request failed",
            )
        )

        log_file = write_correlated_logs(
            trace_id=trace_id,
            shp_span_id=shp_span_id,
            papi_span_id=papi_span_id,
        )

    # shutdown 会等待 BatchSpanProcessor 把缓存中的 Span 发完。
    papi_provider.shutdown()
    shp_provider.shutdown()

    print("Trace 生成完成")
    print("Trace ID：", trace_id)
    print("日志文件：", log_file)
    print(
        "Loki 查询：",
        f'{{job="log-diagnosis-agent"}} |= "{trace_id}"',
    )
    print(
        "Tempo 查询：",
        f"http://localhost:3200/api/traces/{trace_id}",
    )


if __name__ == "__main__":
    generate_trace()