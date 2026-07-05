"""Validation of model-produced file evidence before report publication."""

from dataclasses import dataclass
from pathlib import Path

from repolens.schemas import AnalysisReport, EvidenceRef
from repolens.tools.paths import resolve_within_root


@dataclass(frozen=True)
class EvidenceIssue:
    path: str
    reason: str


class EvidenceValidator:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self._line_counts: dict[Path, int] = {}

    def validate(self, evidence: EvidenceRef) -> EvidenceIssue | None:
        try:
            path = resolve_within_root(self.project_root, evidence.path)
        except ValueError as exc:
            return EvidenceIssue(evidence.path, str(exc))
        if path.is_symlink() or not path.is_file():
            return EvidenceIssue(evidence.path, "evidence path is not a regular file")
        if evidence.line_start is None:
            return None
        try:
            line_count = self._line_counts.setdefault(
                path,
                sum(1 for _ in path.open(encoding="utf-8")),
            )
        except (OSError, UnicodeDecodeError):
            return EvidenceIssue(evidence.path, "evidence file is not readable text")
        line_end = evidence.line_end or evidence.line_start
        if evidence.line_start > line_count or line_end > line_count:
            return EvidenceIssue(
                evidence.path,
                f"line range {evidence.line_start}-{line_end} exceeds {line_count} lines",
            )
        return None

    def keep_valid(self, evidence: list[EvidenceRef]) -> tuple[list[EvidenceRef], list[EvidenceIssue]]:
        valid: list[EvidenceRef] = []
        issues: list[EvidenceIssue] = []
        for item in evidence:
            issue = self.validate(item)
            if issue:
                issues.append(issue)
            else:
                valid.append(item)
        return valid, issues

    def validate_report(self, report: AnalysisReport) -> list[EvidenceIssue]:
        issues: list[EvidenceIssue] = []
        collections = [
            report.evidence,
            *(item.evidence for item in report.tech_stack),
            *(item.evidence for item in report.entry_points),
            *(item.evidence for item in report.module_map),
            *(item.evidence for item in report.call_flows),
            *(item.evidence for item in report.run_commands),
            *(item.evidence for item in report.risks),
        ]
        for collection in collections:
            for item in collection:
                issue = self.validate(item)
                if issue:
                    issues.append(issue)
        return issues
