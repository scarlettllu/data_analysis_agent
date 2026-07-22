"""Track analysis provenance for credibility."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ProvenanceStep:
    step: str
    action: str
    details: str
    sql_or_code: str = ""
    fields_used: list[str] = field(default_factory=list)
    data_source: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AnalysisProvenance:
    question: str
    data_source: str
    steps: list[ProvenanceStep] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    conclusion: str = ""

    def to_markdown(self) -> str:
        lines = [
            "## 分析溯源",
            f"- **问题**: {self.question}",
            f"- **数据源**: {self.data_source}",
            "",
            "### 执行步骤",
        ]
        for i, s in enumerate(self.steps, 1):
            lines.append(f"{i}. **{s.step}** ({s.action})")
            lines.append(f"   - {s.details}")
            if s.fields_used:
                lines.append(f"   - 使用字段: {', '.join(s.fields_used)}")
            if s.sql_or_code:
                lines.append(f"   ```\n   {s.sql_or_code.strip()}\n   ```")
        if self.evidence:
            lines.append("\n### 证据数据")
            for e in self.evidence[:10]:
                lines.append(f"- {e}")
        if self.conclusion:
            lines.append(f"\n### 结论\n{self.conclusion}")
        return "\n".join(lines)


class ProvenanceTracker:
    def __init__(self, question: str, data_source: str):
        self.provenance = AnalysisProvenance(question=question, data_source=data_source)

    def add_step(
        self,
        step: str,
        action: str,
        details: str,
        sql_or_code: str = "",
        fields_used: list[str] | None = None,
    ) -> None:
        self.provenance.steps.append(
            ProvenanceStep(
                step=step,
                action=action,
                details=details,
                sql_or_code=sql_or_code,
                fields_used=fields_used or [],
                data_source=self.provenance.data_source,
            )
        )

    def add_evidence(self, evidence: dict[str, Any]) -> None:
        self.provenance.evidence.append(evidence)

    def set_conclusion(self, conclusion: str) -> None:
        self.provenance.conclusion = conclusion

    def get(self) -> AnalysisProvenance:
        return self.provenance
