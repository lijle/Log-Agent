from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tools.base_tool import BaseTool

class LokiQueryTool(BaseTool):
    """从 Loki 查询业务日志。

    输入：
    - query: LogQL 查询语句
    - limit: 最大返回条数，默认 100
    - lookback_minutes: 查询最近多少分钟，默认 60

    输出：
    - success: 查询是否成功
    - logs: 结构化日志列表
    - raw_logs: 合并后的原始日志文本
    - total: 日志数量
    - error: 错误信息
    """
    name = "loki_query_tool"
    description = (
        "使用 LogQL 从 Loki 查询指定服务、Trace ID 或关键字对应的业务日志。"
    )

    def __init__(self, base_url: str = "http://localhost:3100") -> None:
        """初始化 Loki 工具。

        输入：
        - base_url: Loki HTTP 服务地址

        输出：
        - None
        """
        self.base_url = base_url.rstrip("/")
    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """执行 Loki 范围查询。"""
        query = str(input.get("query", "")).strip()
        limit = int(input.get("limit", 100))
        lookback_minutes = int(input.get("lookback_minutes", 60))

        validation_error = self._validate_input(
            query=query,
            limit=limit,
            lookback_minutes=lookback_minutes,
        )

        if validation_error:
            return self._build_error_result(
                query=query,
                error=validation_error,
            )

        request_url = self._build_request_url(
            query=query,
            limit=limit,
            lookback_minutes=lookback_minutes,
        )

        try:
            response_data = self._send_request(request_url)
            logs = self._extract_logs(response_data)

            return {
                "success": True,
                "query": query,
                "request_url": request_url,
                "logs": logs,
                "raw_logs": self._merge_raw_logs(logs),
                "total": len(logs),
                "error": "",
            }

        except HTTPError as error:
            return self._build_error_result(
                query=query,
                error=f"Loki 返回 HTTP 错误：{error.code} {error.reason}",
            )

        except URLError as error:
            return self._build_error_result(
                query=query,
                error=f"无法连接 Loki：{error.reason}",
            )

        except json.JSONDecodeError:
            return self._build_error_result(
                query=query,
                error="Loki 返回的内容不是合法 JSON。",
            )

        except Exception as error:
            return self._build_error_result(
                query=query,
                error=f"查询 Loki 时发生未知错误：{error}",
            )

    def _validate_input(
        self,
        query: str,
        limit: int,
        lookback_minutes: int,
    ) -> str:
        """检查工具输入是否合法。"""
        if not query:
            return "query 不能为空。"

        if limit < 1 or limit > 1000:
            return "limit 必须在 1 到 1000 之间。"

        if lookback_minutes < 1:
            return "lookback_minutes 必须大于 0。"

        return ""

    def _build_request_url(
        self,
        query: str,
        limit: int,
        lookback_minutes: int,
    ) -> str:
        """构造 Loki query_range 请求地址。"""
        end_time_ns = time.time_ns()
        start_time_ns = end_time_ns - lookback_minutes * 60 * 1_000_000_000

        query_parameters = {
            "query": query,
            "start": str(start_time_ns),
            "end": str(end_time_ns),
            "limit": str(limit),
            "direction": "backward",
        }

        encoded_parameters = urlencode(query_parameters)

        return (
            f"{self.base_url}/loki/api/v1/query_range"
            f"?{encoded_parameters}"
        )

    def _send_request(self, request_url: str) -> dict[str, Any]:
        """向 Loki 发送 HTTP GET 请求。"""
        request = Request(
            url=request_url,
            headers={"Accept": "application/json"},
            method="GET",
        )

        with urlopen(request, timeout=10) as response:
            response_text = response.read().decode("utf-8")
            return json.loads(response_text)

    def _extract_logs(
        self,
        response_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """把 Loki 的流式返回结果整理成普通日志列表。"""
        logs: list[dict[str, Any]] = []

        result_streams = (
            response_data
            .get("data", {})
            .get("result", [])
        )

        for result_stream in result_streams:
            labels = result_stream.get("stream", {})
            values = result_stream.get("values", [])

            for value in values:
                timestamp_ns = value[0]
                log_line = value[1]

                log_item = {
                    "timestamp_ns": timestamp_ns,
                    "timestamp": self._format_timestamp(timestamp_ns),
                    "line": log_line,
                    "labels": labels,
                }

                logs.append(log_item)

        # Agent 阅读日志时，按照时间从旧到新更容易理解事件发展。
        logs.sort(key=lambda item: int(item["timestamp_ns"]))

        return logs

    def _format_timestamp(self, timestamp_ns: str) -> str:
        """把 Loki 的纳秒时间戳转换成可读时间。"""
        timestamp_seconds = int(timestamp_ns) / 1_000_000_000

        return datetime.fromtimestamp(
            timestamp_seconds,
            tz=timezone.utc,
        ).isoformat()

    def _merge_raw_logs(
        self,
        logs: list[dict[str, Any]],
    ) -> str:
        """将多条日志合并成日志解析器可处理的文本。"""
        log_lines: list[str] = []

        for log_item in logs:
            log_lines.append(str(log_item.get("line", "")))

        return "\n".join(log_lines)

    def _build_error_result(
        self,
        query: str,
        error: str,
    ) -> dict[str, Any]:
        """构造统一的失败返回结果。"""
        return {
            "success": False,
            "query": query,
            "request_url": "",
            "logs": [],
            "raw_logs": "",
            "total": 0,
            "error": error,
        }
