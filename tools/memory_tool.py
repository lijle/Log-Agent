from __future__ import annotations

from typing import Any

from memory.sqlite_memory import SQLiteMemory
from tools.base_tool import BaseTool


class MemoryTool(BaseTool):
    name = "memory_tool"
    description = "Store and search historical diagnosis cases in SQLite."

    def __init__(self, memory_store: SQLiteMemory) -> None:
        self.memory_store = memory_store

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        action = input.get("action")
        if action == "add_case":
            case_id = self.memory_store.add_case(
                raw_log_summary=input.get("raw_log_summary", ""),
                extracted_fields=input.get("extracted_fields", {}),
                diagnosis_summary=input.get("diagnosis_summary", ""),
                root_causes=input.get("root_causes", []),
                troubleshooting_steps=input.get("troubleshooting_steps", []),
            )
            return {"status": "ok", "case_id": case_id}

        if action == "search_cases":
            cases = self.memory_store.search_cases(
                query=input.get("query", ""),
                limit=int(input.get("limit", 3)),
            )
            return {"status": "ok", "cases": cases}

        if action == "list_recent_cases":
            cases = self.memory_store.list_recent_cases(limit=int(input.get("limit", 5)))
            return {"status": "ok", "cases": cases}

        return {"status": "error", "message": f"unsupported action: {action}"}
