from pathlib import Path

from memory.sqlite_memory import SQLiteMemory


def test_sqlite_memory_add_and_search(tmp_path: Path) -> None:
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
