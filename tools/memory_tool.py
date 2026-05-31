from __future__ import annotations

from typing import Any

from memory.sqlite_memory import SQLiteMemory
from tools.base_tool import BaseTool


class MemoryTool(BaseTool):
    """历史案例记忆工具。

    作用：
    - 对 SQLiteMemory 再包一层统一工具接口
    - 给 Agent 提供 add/search/list 三种动作
    """

    name = "memory_tool"
    description = "Store and search historical diagnosis cases in SQLite."

    def __init__(self, memory_store: SQLiteMemory) -> None:
        """初始化 MemoryTool。

        输入：
        - memory_store：底层 SQLite 记忆库实例

        输出：
        - None
        """

        self.memory_store = memory_store

    def run(self, input: dict[str, Any]) -> dict[str, Any]:
        """根据 action 分发到不同的记忆操作。

        输入：
        - input：需要包含 `action`，可选值为 `add_case`、`search_cases`、`list_recent_cases`

        输出：
        - dict[str, Any]：成功时返回 `status=ok` 和结果；
          不支持的 action 返回错误信息
        """

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
