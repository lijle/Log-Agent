from __future__ import annotations

from typing import Any

def check_exception_type_match(
    predicted_exception_type: str,
    expected_exception_type: str,
) -> bool:
    """检查异常类型是否匹配。"""
    return predicted_exception_type == expected_exception_type

def check_root_cause_hit(
    root_causes: list[str],
    expected_keywords: list[str],
) -> bool:
    """检查根因列表是否命中预期关键词。"""
    joined_root_causes = " ".join(root_causes)
    for keyword in expected_keywords:
        if keyword in joined_root_causes:
            return True
    return False

def collect_actual_evidence_types(
    root_cause_candidates: list[dict[str, Any]],
) -> set[str]:
    """从 root_cause_candidates 中收集实际出现的证据类型。"""
    actual_evidence_types: set[str] = set()

    for candidate in root_cause_candidates:
        evidence_list = candidate.get("evidence", [])
        for evidence in evidence_list:
            evidence_type = evidence.get("evidence_type", "")
            if evidence_type:
                actual_evidence_types.add(evidence_type)

    return actual_evidence_types

def check_evidence_coverage(
    root_cause_candidates: list[dict[str, Any]],
    expected_evidence_types: list[str],
) -> tuple[bool, list[str]]:
    """检查证据类型是否覆盖预期要求。"""
    actual_evidence_types = collect_actual_evidence_types(root_cause_candidates)
    expected_set = set(expected_evidence_types)
    covered = expected_set.issubset(actual_evidence_types)
    return covered, sorted(actual_evidence_types)

def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """根据逐 case 结果生成汇总统计。"""
    total_cases = len(results)
    if total_cases == 0:
        return {
            "total_cases": 0,
            "exception_type_accuracy": 0.0,
            "root_cause_hit_rate": 0.0,
            "evidence_coverage_rate": 0.0,
        }

    exception_type_match_count = 0
    root_cause_hit_count = 0
    evidence_coverage_count = 0

    for item in results:
        if item.get("exception_type_match", False):
            exception_type_match_count += 1
        if item.get("root_cause_hit", False):
            root_cause_hit_count += 1
        if item.get("evidence_coverage", False):
            evidence_coverage_count += 1

    return {
        "total_cases": total_cases,
        "exception_type_accuracy": round(exception_type_match_count / total_cases, 2),
        "root_cause_hit_rate": round(root_cause_hit_count / total_cases, 2),
        "evidence_coverage_rate": round(evidence_coverage_count / total_cases, 2),
    }