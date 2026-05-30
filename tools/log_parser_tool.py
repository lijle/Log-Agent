from __future__ import annotations

from typing import Any

from parser.log_parser import parse_log
from tools.base_tool import BaseTool


class LogParserTool(BaseTool):
    name = "log_parser_tool"
    description = "Parse raw application logs and extract structured error fields."

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        raw_log = input.get("raw_log", "")
        if not raw_log:
            return {"error": "raw_log is required", "extracted_fields": {}, "log_summary": ""}
        return parse_log(raw_log)
