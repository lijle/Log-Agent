from __future__ import annotations

from typing import Any

from parser.log_parser import parse_log
from tools.base_tool import BaseTool


class LogParserTool(BaseTool):
    """日志解析工具。

    作用：
    - 调用 parser 层的 `parse_log`
    - 把原始日志转成结构化字段和日志摘要
    """

    name = "log_parser_tool"
    description = "Parse raw application logs and extract structured error fields."

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """执行日志解析。

        输入：
        - input：至少应包含 `raw_log` 字段

        输出：
        - dict[str, Any]：成功时返回 extracted_fields、log_summary、evidence_lines；
          若缺少 raw_log，则返回错误信息和空结果
        """

        raw_log = input.get("raw_log", "")
        if not raw_log:
            return {"error": "raw_log is required", "extracted_fields": {}, "log_summary": ""}
        return parse_log(raw_log)
