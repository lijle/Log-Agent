from __future__ import annotations

import re
from typing import Any


TIMESTAMP_PATTERNS = [
    r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d{3}|.\d{3})?(?:Z)?\b",
    r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\b",
]
LEVEL_PATTERN = r"\b(DEBUG|INFO|WARN|WARNING|ERROR|FATAL|TRACE)\b"
SERVICE_PATTERNS = [
    r"service[=:]\s*([a-zA-Z0-9._-]+)",
    r"\[([a-zA-Z0-9._-]+-service)\]",
    r"\b([a-zA-Z0-9._-]+-service)\b",
]
TRACE_PATTERNS = [
    r"(?:trace_id|traceId|request_id|requestId|correlation_id|correlationId)[=:]\s*([a-zA-Z0-9-]+)",
]
EXCEPTION_PATTERN = r"\b([A-Z][a-zA-Z0-9]+(?:Exception|Error))\b"
STATUS_PATTERNS = [
    r"\bstatus(?:_code)?[=:]\s*(\d{3})\b",
    r"\bhttp(?:\s+status)?[=:]?\s*(\d{3})\b",
    r"\bresponse(?:\s+code)?[=:]\s*(\d{3})\b",
]


def _first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return next((group for group in match.groups() if group), match.group(0))
    return None


def _extract_timestamp(text: str) -> str | None:
    return _first_match(TIMESTAMP_PATTERNS, text)


def _extract_level(text: str) -> str | None:
    match = re.search(LEVEL_PATTERN, text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else None


def _extract_service(text: str) -> str | None:
    return _first_match(SERVICE_PATTERNS, text)


def _extract_trace_id(text: str) -> str | None:
    return _first_match(TRACE_PATTERNS, text)


def _extract_exception(text: str) -> str | None:
    match = re.search(EXCEPTION_PATTERN, text)
    return match.group(1) if match else None


def _extract_status_code(text: str) -> int | None:
    for pattern in STATUS_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1)
        try:
            code = int(value)
        except ValueError:
            continue
        if 100 <= code <= 599:
            return code
    return None


def _extract_error_message(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    priority_tokens = ["exception", "failed", "timeout", "denied", "not available", "unauthorized"]
    error_like = [
        line for line in lines if any(token in line.lower() for token in priority_tokens)
    ]
    if not error_like:
        error_like = [
            line
            for line in lines
            if any(token in line.lower() for token in ["error", "warn", "fatal"])
        ]
    target = error_like[0] if error_like else (lines[0] if lines else "")
    if ":" in target:
        message = target.split(":", 1)[1].strip()
        return message or target[:240]
    return target[:240] if target else None


def parse_log(raw_log: str) -> dict[str, Any]:
    text = raw_log.strip()
    extracted_fields = {
        "timestamp": _extract_timestamp(text),
        "log_level": _extract_level(text),
        "service_name": _extract_service(text),
        "trace_id": _extract_trace_id(text),
        "exception_type": _extract_exception(text),
        "error_message": _extract_error_message(text),
        "http_status_code": _extract_status_code(text),
    }

    summary_parts = [
        extracted_fields.get("service_name") or "unknown-service",
        extracted_fields.get("log_level") or "UNKNOWN",
        extracted_fields.get("exception_type") or "generic error",
        extracted_fields.get("error_message") or "no error message",
    ]
    log_summary = " | ".join(summary_parts)

    evidence_lines = [line.strip() for line in text.splitlines() if line.strip()][:5]
    return {
        "extracted_fields": extracted_fields,
        "log_summary": log_summary,
        "evidence_lines": evidence_lines,
    }
