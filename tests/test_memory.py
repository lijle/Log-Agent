from pathlib import Path

from memory.sqlite_memory import SQLiteMemory


def test_sqlite_memory_add_and_search(tmp_path: Path) -> None:
    """验证 SQLiteMemory 的新增和搜索能力。

    作用：
    - 确认案例能成功写入 SQLite
    - 确认后续可以通过关键词搜索回该案例

    输入：
    - tmp_path：pytest 提供的临时目录

    输出：
    - None：断言通过则表示测试成功
    """

    db_path = tmp_path / "memory.db"
    memory = SQLiteMemory(db_path)

    case_id = memory.add_case(
        raw_log_summary="order-service timeout ReadTimeoutException",
        extracted_fields={"service_name": "order-service", "exception_type": "ReadTimeoutException"},
        diagnosis_summary="downstream timeout issue",
        root_causes=["downstream latency spike"],
        troubleshooting_steps=["check downstream latency"],
    )

    assert case_id.startswith("case-")

    results = memory.search_cases("ReadTimeoutException", limit=2)
    assert len(results) == 1
    assert results[0]["diagnosis_summary"] == "downstream timeout issue"
