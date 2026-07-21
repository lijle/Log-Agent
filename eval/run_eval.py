from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agent.langgraph_agent import LangGraphAgent
from eval.metrics import (
    build_summary,
    check_evidence_coverage,
    check_exception_type_match,
    check_root_cause_hit,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = PROJECT_ROOT / "eval" / "cases"
OUTPUT_PATH = PROJECT_ROOT / "eval" / "eval_results.json"


def load_cases() -> list[dict[str, Any]]:
    """加载所有评估用例。"""
    cases: list[dict[str, Any]] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        content = path.read_text(encoding="utf-8")
        case_data = json.loads(content)
        cases.append(case_data)
    return cases


def evaluate_case(agent: LangGraphAgent, case: dict[str, Any]) -> dict[str, Any]:
    """运行单个 case，并返回评估结果。"""
    result = agent.run(case["raw_log"])

    parsed_fields = result.get("parsed_result", {}).get("extracted_fields", {})
    report_result = result.get("report_result", {})
    root_causes = report_result.get("root_causes", [])
    root_cause_candidates = report_result.get("root_cause_candidates", [])

    predicted_exception_type = parsed_fields.get("exception_type", "")
    expected_exception_type = case.get("expected_exception_type", "")
    expected_keywords = case.get("expected_root_cause_keywords", [])
    expected_evidence_types = case.get("expected_required_evidence", [])

    exception_type_match = check_exception_type_match(
        predicted_exception_type=predicted_exception_type,
        expected_exception_type=expected_exception_type,
    )
    root_cause_hit = check_root_cause_hit(
        root_causes=root_causes,
        expected_keywords=expected_keywords,
    )
    evidence_coverage, actual_evidence_types = check_evidence_coverage(
        root_cause_candidates=root_cause_candidates,
        expected_evidence_types=expected_evidence_types,
    )

    return {
        "case_id": case["case_id"],
        "exception_type_match": exception_type_match,
        "root_cause_hit": root_cause_hit,
        "evidence_coverage": evidence_coverage,
        "predicted_exception_type": predicted_exception_type,
        "expected_exception_type": expected_exception_type,
        "actual_evidence_types": actual_evidence_types,
        "expected_evidence_types": sorted(expected_evidence_types),
    }


def main() -> None:
    """批量运行评估。"""
    load_dotenv(PROJECT_ROOT / ".env")

    agent = LangGraphAgent()
    cases = load_cases()

    results: list[dict[str, Any]] = []
    for case in cases:
        print(f"[Eval] 开始评估: {case['case_id']}")
        case_result = evaluate_case(agent, case)
        results.append(case_result)
        print(f"[Eval] 完成评估: {case['case_id']}")

    summary = build_summary(results)

    final_output = {
        "summary": summary,
        "results": results,
    }

    OUTPUT_PATH.write_text(
        json.dumps(final_output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"评估完成，共 {summary['total_cases']} 个 case。")
    print(f"异常类型准确率: {summary['exception_type_accuracy']}")
    print(f"根因命中率: {summary['root_cause_hit_rate']}")
    print(f"证据覆盖率: {summary['evidence_coverage_rate']}")
    print(f"结果已写入: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()