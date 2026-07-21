from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass
class Evidence:
    """表示一条诊断证据。"""
    evidence_type: str
    content: str
    source: str
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转成可序列化字典。"""
        return asdict(self)

@dataclass
class RootCauseCandidate:
    """表示一个候选根因及其证据。"""

    hypothesis: str
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 0.0
    missing_evidence: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转成可序列化字典。"""
        return {
            "hypothesis": self.hypothesis,
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence,
            "missing_evidence": self.missing_evidence,
            "next_actions": self.next_actions,
        }