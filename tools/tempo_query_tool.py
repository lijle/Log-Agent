from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import base64
from tools.base_tool import BaseTool


class TempoQueryTool(BaseTool):
    """根据 Trace ID 从 Tempo 查询完整调用链。"""

    name = "tempo_query_tool"
    description = (
        "根据 Trace ID 查询 Tempo，返回服务、Span、父子关系、"
        "耗时、状态和错误信息。"
    )

    def __init__(
        self,
        base_url: str = "http://localhost:3200",
    ) -> None:
        """保存 Tempo HTTP 地址。"""
        self.base_url = base_url.rstrip("/")

    def run(
        self,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        """执行一次 Tempo Trace 查询。

        输入：
        - trace_id: 16或32位十六进制 Trace ID

        输出：
        - spans: 展平后的 Span
        - service_names: Trace 涉及的服务
        - error_spans: 状态为 ERROR 的 Span
        - timeline: 按父子关系整理的时间线
        """
        trace_id = str(
            input.get("trace_id", "")
        ).strip().lower()

        validation_error = self._validate_trace_id(
            trace_id
        )

        if validation_error:
            return self._build_error_result(
                trace_id=trace_id,
                error=validation_error,
            )

        request_url = (
            f"{self.base_url}/api/traces/{trace_id}"
        )

        try:
            response_data = self._send_request(
                request_url
            )

            spans = self._extract_spans(
                response_data
            )

            service_names = (
                self._extract_service_names(spans)
            )

            error_spans = self._extract_error_spans(
                spans
            )

            timeline = self._build_timeline(
                spans
            )

            return {
                "success": True,
                "trace_id": trace_id,
                "request_url": request_url,
                "total_spans": len(spans),
                "service_names": service_names,
                "spans": spans,
                "error_spans": error_spans,
                "timeline": timeline,
                "timeline_text": "\n".join(timeline),
                "error": "",
            }

        except HTTPError as error:
            if error.code == 404:
                error_message = (
                    "Tempo 中没有找到该 Trace ID。"
                )
            else:
                error_message = (
                    f"Tempo 返回 HTTP 错误："
                    f"{error.code} {error.reason}"
                )

            return self._build_error_result(
                trace_id=trace_id,
                error=error_message,
            )

        except URLError as error:
            return self._build_error_result(
                trace_id=trace_id,
                error=(
                    f"无法连接 Tempo：{error.reason}"
                ),
            )

        except json.JSONDecodeError:
            return self._build_error_result(
                trace_id=trace_id,
                error="Tempo 返回的内容不是合法 JSON。",
            )

        except Exception as error:
            return self._build_error_result(
                trace_id=trace_id,
                error=f"查询 Tempo 时发生异常：{error}",
            )

    def _validate_trace_id(
        self,
        trace_id: str,
    ) -> str:
        """检查 Trace ID 是否为合法十六进制字符串。"""
        if not trace_id:
            return "trace_id 不能为空。"

        if not re.fullmatch(
            r"[0-9a-f]{16}|[0-9a-f]{32}",
            trace_id,
        ):
            return (
                "trace_id 必须是16位或32位"
                "十六进制字符串。"
            )

        return ""

    def _send_request(
        self,
        request_url: str,
    ) -> dict[str, Any]:
        """向 Tempo 发送 HTTP GET 请求。"""
        request = Request(
            url=request_url,
            headers={
                "Accept": "application/json",
            },
            method="GET",
        )

        with urlopen(
            request,
            timeout=10,
        ) as response:
            response_text = (
                response.read().decode("utf-8")
            )

        return json.loads(response_text)

    def _extract_spans(
        self,
        response_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """将 Tempo 的嵌套结构展平成 Span 列表。"""
        spans: list[dict[str, Any]] = []

        batches = response_data.get(
            "batches",
            [],
        )

        for batch in batches:
            resource = batch.get(
                "resource",
                {},
            )

            resource_attributes = (
                self._extract_attributes(
                    resource.get("attributes", [])
                )
            )

            service_name = str(
                resource_attributes.get(
                    "service.name",
                    "unknown-service",
                )
            )

            scope_spans_list = batch.get(
                "scopeSpans",
                [],
            )

            for scope_spans in scope_spans_list:
                raw_spans = scope_spans.get(
                    "spans",
                    [],
                )

                for raw_span in raw_spans:
                    span = self._convert_span(
                        raw_span=raw_span,
                        service_name=service_name,
                        resource_attributes=(
                            resource_attributes
                        ),
                    )

                    spans.append(span)

        spans.sort(
            key=lambda item: item["start_time_ns"]
        )

        return spans

    def _convert_span(
        self,
        raw_span: dict[str, Any],
        service_name: str,
        resource_attributes: dict[str, Any],
    ) -> dict[str, Any]:
        """将一个 Tempo 原始 Span 转换成简化结构。"""
        start_time_ns = int(
            raw_span.get(
                "startTimeUnixNano",
                0,
            )
        )

        end_time_ns = int(
            raw_span.get(
                "endTimeUnixNano",
                0,
            )
        )

        duration_ms = (
            end_time_ns - start_time_ns
        ) / 1_000_000

        status = self._normalize_status(
            raw_span.get("status", {})
        )

        span_attributes = (
            self._extract_attributes(
                raw_span.get("attributes", [])
            )
        )

        events = self._extract_events(
            raw_span.get("events", [])
        )

        return {
            "trace_id": self._normalize_identifier(
                raw_span.get("traceId", "")
            ),
            "span_id": self._normalize_identifier(
                raw_span.get("spanId", "")
            ),
            "parent_span_id": self._normalize_identifier(
                raw_span.get("parentSpanId", "")
            ),
            "service_name": service_name,
            "operation_name": raw_span.get(
                "name",
                "",
            ),
            "kind": self._normalize_kind(
                raw_span.get("kind")
            ),
            "status": status,
            "status_message": (
                raw_span
                .get("status", {})
                .get("message", "")
            ),
            "start_time_ns": start_time_ns,
            "start_time": self._format_timestamp(
                start_time_ns
            ),
            "duration_ms": round(
                duration_ms,
                3,
            ),
            "attributes": span_attributes,
            "resource_attributes": (
                resource_attributes
            ),
            "events": events,
        }

    def _extract_attributes(
        self,
        raw_attributes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """将 OTLP attributes 数组转换成普通字典。"""
        attributes: dict[str, Any] = {}

        for raw_attribute in raw_attributes:
            key = str(
                raw_attribute.get("key", "")
            )

            value_container = raw_attribute.get(
                "value",
                {},
            )

            value = self._extract_attribute_value(
                value_container
            )

            if key:
                attributes[key] = value

        return attributes

    def _extract_attribute_value(
        self,
        value_container: dict[str, Any],
    ) -> Any:
        """读取 OTLP 属性中真正的值。"""
        possible_keys = [
            "stringValue",
            "intValue",
            "doubleValue",
            "boolValue",
            "bytesValue",
        ]

        for key in possible_keys:
            if key in value_container:
                return value_container[key]

        return value_container

    def _extract_events(
        self,
        raw_events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """提取 Span 事件，例如 exception 事件。"""
        events: list[dict[str, Any]] = []

        for raw_event in raw_events:
            event = {
                "name": raw_event.get(
                    "name",
                    "",
                ),
                "attributes": (
                    self._extract_attributes(
                        raw_event.get(
                            "attributes",
                            [],
                        )
                    )
                ),
            }

            events.append(event)

        return events

    def _normalize_identifier(
            self,
            raw_identifier: Any,
    ) -> str:
        """将 Tempo 的 Base64 ID 转换成十六进制 ID。"""
        identifier_text = str(
            raw_identifier or ""
        ).strip()

        if not identifier_text:
            return ""

        if re.fullmatch(
                r"[0-9a-fA-F]+",
                identifier_text,
        ):
            return identifier_text.lower()

        try:
            identifier_bytes = base64.b64decode(
                identifier_text,
                validate=True,
            )

            return identifier_bytes.hex()

        except (ValueError, TypeError):
            return identifier_text

    def _normalize_status(
        self,
        raw_status: dict[str, Any],
    ) -> str:
        """把 OTLP 状态码转换成易读文本。"""
        status_code = raw_status.get(
            "code",
            0,
        )

        status_text = str(
            status_code
        ).upper()

        if status_text in {
            "2",
            "STATUS_CODE_ERROR",
            "ERROR",
        }:
            return "ERROR"

        if status_text in {
            "1",
            "STATUS_CODE_OK",
            "OK",
        }:
            return "OK"

        return "UNSET"

    def _normalize_kind(
        self,
        raw_kind: Any,
    ) -> str:
        """把 OTLP SpanKind 转换成易读文本。"""
        kind_mapping = {
            "0": "UNSPECIFIED",
            "1": "INTERNAL",
            "2": "SERVER",
            "3": "CLIENT",
            "4": "PRODUCER",
            "5": "CONSUMER",
        }

        kind_text = str(
            raw_kind
        ).upper()

        if kind_text in kind_mapping:
            return kind_mapping[kind_text]

        return kind_text.replace(
            "SPAN_KIND_",
            "",
        )

    def _format_timestamp(
        self,
        timestamp_ns: int,
    ) -> str:
        """将纳秒时间戳转换成 UTC 时间。"""
        if timestamp_ns <= 0:
            return ""

        timestamp_seconds = (
            timestamp_ns / 1_000_000_000
        )

        return datetime.fromtimestamp(
            timestamp_seconds,
            tz=timezone.utc,
        ).isoformat()

    def _extract_service_names(
        self,
        spans: list[dict[str, Any]],
    ) -> list[str]:
        """从 Span 列表提取服务名称并去重。"""
        service_names: list[str] = []

        for span in spans:
            service_name = str(
                span.get(
                    "service_name",
                    "",
                )
            )

            if not service_name:
                continue

            if service_name in service_names:
                continue

            service_names.append(service_name)

        return service_names

    def _extract_error_spans(
        self,
        spans: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """提取状态为 ERROR 的 Span。"""
        error_spans: list[dict[str, Any]] = []

        for span in spans:
            if span.get("status") == "ERROR":
                error_spans.append(span)

        return error_spans

    def _build_timeline(
            self,
            spans: list[dict[str, Any]],
    ) -> list[str]:
        """根据 Span 父子关系构造根节点优先的调用链。"""
        span_by_id: dict[str, dict[str, Any]] = {}

        for span in spans:
            span_id = str(
                span.get("span_id", "")
            )

            if span_id:
                span_by_id[span_id] = span

        root_spans: list[dict[str, Any]] = []
        children_by_parent: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        for span in spans:
            parent_span_id = str(
                span.get("parent_span_id", "")
            )

            if parent_span_id in span_by_id:
                children = children_by_parent.setdefault(
                    parent_span_id,
                    [],
                )
                children.append(span)
            else:
                root_spans.append(span)

        root_spans.sort(
            key=lambda item: item["start_time_ns"]
        )

        for children in children_by_parent.values():
            children.sort(
                key=lambda item: item["start_time_ns"]
            )

        timeline: list[str] = []

        # stack 保存“接下来处理哪个 Span，以及它应该缩进几层”。
        stack: list[tuple[dict[str, Any], int]] = []

        for root_span in reversed(root_spans):
            stack.append(
                (root_span, 0)
            )

        while stack:
            span, depth = stack.pop()

            indentation = "  " * depth

            timeline_line = (
                f"{indentation}"
                f"- [{span['status']}] "
                f"{span['service_name']} | "
                f"{span['operation_name']} | "
                f"{span['duration_ms']}ms | "
                f"span={span['span_id']}"
            )

            timeline.append(timeline_line)

            span_id = str(
                span.get("span_id", "")
            )

            children = children_by_parent.get(
                span_id,
                [],
            )

            # 栈是后进先出，因此需要倒序放入，取出时才保持正确顺序。
            for child_span in reversed(children):
                stack.append(
                    (child_span, depth + 1)
                )

        return timeline

    def _calculate_depth(
        self,
        span: dict[str, Any],
        span_by_id: dict[str, dict[str, Any]],
    ) -> int:
        """沿 parent_span_id 向上查找，计算 Span 深度。"""
        depth = 0
        parent_span_id = str(
            span.get("parent_span_id", "")
        )

        visited_span_ids: set[str] = set()

        while parent_span_id in span_by_id:
            if parent_span_id in visited_span_ids:
                break

            visited_span_ids.add(
                parent_span_id
            )

            depth += 1

            parent_span = span_by_id[
                parent_span_id
            ]

            parent_span_id = str(
                parent_span.get(
                    "parent_span_id",
                    "",
                )
            )

        return depth

    def _build_error_result(
        self,
        trace_id: str,
        error: str,
    ) -> dict[str, Any]:
        """构造统一的失败结果。"""
        return {
            "success": False,
            "trace_id": trace_id,
            "request_url": "",
            "total_spans": 0,
            "service_names": [],
            "spans": [],
            "error_spans": [],
            "timeline": [],
            "timeline_text": "",
            "error": error,
        }