from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SQLiteMemory:
    """基于 SQLite 的历史诊断记忆库。

    作用：
    - 把每次诊断结果保存到本地 `.db` 文件
    - 支持搜索相似历史案例
    - 支持列出最近案例，供 UI 和 Agent 使用
    """

    def __init__(self, db_path: Path) -> None:
        """初始化 SQLite 记忆库。

        输入：
        - db_path：SQLite 数据库文件路径

        输出：
        - None：会自动创建目录并初始化表结构
        """

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """创建一个 SQLite 连接。

        输出：
        - sqlite3.Connection：指向当前数据库文件的连接对象
        """

        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """初始化数据库表结构。

        作用：
        - 如果 `diagnosis_cases` 表不存在，则自动创建

        输出：
        - None
        """

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS diagnosis_cases (
                    case_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    raw_log_summary TEXT NOT NULL,
                    extracted_fields TEXT NOT NULL,
                    diagnosis_summary TEXT NOT NULL,
                    root_causes TEXT NOT NULL,
                    troubleshooting_steps TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def add_case(
        self,
        raw_log_summary: str,
        extracted_fields: dict[str, Any],
        diagnosis_summary: str,
        root_causes: list[str],
        troubleshooting_steps: list[str],
    ) -> str:
        """新增一条历史诊断案例。

        输入：
        - raw_log_summary：日志摘要
        - extracted_fields：结构化日志字段
        - diagnosis_summary：诊断结论摘要
        - root_causes：可能根因列表
        - troubleshooting_steps：排查步骤列表

        输出：
        - str：新生成的 case_id
        """

        case_id = f"case-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO diagnosis_cases (
                    case_id, created_at, raw_log_summary, extracted_fields,
                    diagnosis_summary, root_causes, troubleshooting_steps
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    created_at,
                    raw_log_summary,
                    json.dumps(extracted_fields, ensure_ascii=False),
                    diagnosis_summary,
                    json.dumps(root_causes, ensure_ascii=False),
                    json.dumps(troubleshooting_steps, ensure_ascii=False),
                ),
            )
            conn.commit()
        return case_id

    def search_cases(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """按关键词模糊搜索历史案例。

        作用：
        - 在摘要、诊断结论和提取字段 JSON 中做 LIKE 匹配

        输入：
        - query：搜索关键词
        - limit：最多返回多少条

        输出：
        - list[dict[str, Any]]：历史案例列表
        """

        like_query = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT case_id, created_at, raw_log_summary, extracted_fields,
                       diagnosis_summary, root_causes, troubleshooting_steps
                FROM diagnosis_cases
                WHERE raw_log_summary LIKE ?
                   OR diagnosis_summary LIKE ?
                   OR extracted_fields LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (like_query, like_query, like_query, limit),
            ).fetchall()
        return [self._row_to_case(row) for row in rows]

    def list_recent_cases(self, limit: int = 5) -> list[dict[str, Any]]:
        """列出最近保存的案例。

        输入：
        - limit：返回条数上限

        输出：
        - list[dict[str, Any]]：按时间倒序排列的案例列表
        """

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT case_id, created_at, raw_log_summary, extracted_fields,
                       diagnosis_summary, root_causes, troubleshooting_steps
                FROM diagnosis_cases
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_case(row) for row in rows]

    @staticmethod
    def _row_to_case(row: tuple[Any, ...]) -> dict[str, Any]:
        """把 SQLite 行数据转换成 Python 字典。

        作用：
        - 将 JSON 字符串字段反序列化为 dict/list
        - 便于上层直接使用

        输入：
        - row：数据库查询返回的一行元组

        输出：
        - dict[str, Any]：结构化案例对象
        """

        return {
            "case_id": row[0],
            "created_at": row[1],
            "raw_log_summary": row[2],
            "extracted_fields": json.loads(row[3]),
            "diagnosis_summary": row[4],
            "root_causes": json.loads(row[5]),
            "troubleshooting_steps": json.loads(row[6]),
        }
