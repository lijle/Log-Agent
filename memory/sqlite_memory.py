from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SQLiteMemory:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
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
        return {
            "case_id": row[0],
            "created_at": row[1],
            "raw_log_summary": row[2],
            "extracted_fields": json.loads(row[3]),
            "diagnosis_summary": row[4],
            "root_causes": json.loads(row[5]),
            "troubleshooting_steps": json.loads(row[6]),
        }
