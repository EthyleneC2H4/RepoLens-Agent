"""Evidence-aware Markdown and JSON output for analysis reports."""

from pathlib import Path
from typing import Iterable

from repolens.evidence import EvidenceValidator
from repolens.errors import AnalysisError, AnalysisErrorCode
from repolens.schemas import AnalysisReport, EvidenceRef
from repolens.schemas import EntryPoint, ModuleInfo


def _evidence_suffix(items: Iterable[EvidenceRef]) -> str:
    refs = []
    for item in items:
        location = item.path
        if item.line_start:
            location += f":{item.line_start}"
            if item.line_end and item.line_end != item.line_start:
                location += f"-{item.line_end}"
        refs.append(f"`{location}`")
    return f" Evidence: {', '.join(refs)}" if refs else ""


def render_markdown(report: AnalysisReport) -> str:
    lines = ["# RepoLens Analysis Report", "", report.project_summary, ""]
    sections = [
        ("Technology Stack", [f"- **{x.name}** ({x.category})" + (f": {x.version}" if x.version else "") + _evidence_suffix(x.evidence) for x in report.tech_stack]),
        ("Entry Points", [f"- `{x.path}` — {x.description}." + _evidence_suffix(x.evidence) for x in report.entry_points]),
        ("Module Map", [f"- `{x.path}/` — {x.purpose}." + _evidence_suffix(x.evidence) for x in report.module_map]),
        ("Call Flows", [f"- **{x.name}:** " + " → ".join(x.steps) + "." + _evidence_suffix(x.evidence) for x in report.call_flows]),
        ("Run Commands", [f"- `{x.command}` — {x.purpose}." + _evidence_suffix(x.evidence) for x in report.run_commands]),
        ("Risks", [f"- **{x.level.upper()}** — {x.description}." + _evidence_suffix(x.evidence) for x in report.risks]),
        ("Recommended Reading Order", [f"{index}. `{path}`" for index, path in enumerate(report.reading_path, 1)]),
        ("File Evidence", [f"- `{x.path}` — {x.claim}" for x in report.evidence]),
    ]
    for heading, items in sections:
        lines.extend([f"## {heading}", "", *(items or ["_Unknown — no verified evidence._"]), ""])
    metadata = report.metadata
    lines.extend(
        [
            "## Analysis Metadata",
            "",
            f"- Mode: `{metadata.mode}`",
            f"- Model: `{metadata.model or 'none'}`",
            f"- Files scanned: {metadata.files_scanned}",
            f"- Directories scanned: {metadata.directories_scanned}",
            f"- Manifests parsed: {metadata.manifests_parsed}",
            f"- Model tokens: {metadata.tokens}",
            f"- Tool/model calls: {metadata.tool_calls}",
            f"- Duration: {metadata.duration_ms} ms",
            f"- Generated at: {metadata.generated_at.isoformat()}",
            "",
        ]
    )
    return "\n".join(lines)


def assert_report_grounded(report: AnalysisReport) -> None:
    if report.metadata.mode != "standard":
        return
    validator = EvidenceValidator(report.metadata.source_root)
    issues = validator.validate_report(report)
    ungrounded = []
    for section in (
        report.tech_stack,
        report.entry_points,
        report.module_map,
        report.call_flows,
        report.run_commands,
        report.risks,
    ):
        ungrounded.extend(item for item in section if not item.evidence)
    invalid_paths = [
        item.path
        for item in report.entry_points
        if not validator.path_exists(item.path)
    ]
    invalid_paths.extend(
        item.path
        for item in report.module_map
        if not validator.path_exists(item.path, allow_directory=True)
    )
    invalid_paths.extend(path for path in report.reading_path if not validator.path_exists(path))
    if issues or ungrounded or invalid_paths:
        details = [f"{issue.path}: {issue.reason}" for issue in issues]
        details.extend(type(item).__name__ for item in ungrounded)
        details.extend(f"invalid report path: {path}" for path in invalid_paths)
        raise AnalysisError(
            AnalysisErrorCode.EVIDENCE_INVALID,
            "report contains invalid or missing evidence: " + "; ".join(details),
        )


def write_report(report: AnalysisReport, output_dir: Path, output_format: str) -> list[Path]:
    assert_report_grounded(report)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if output_format in {"md", "both"}:
        path = output_dir / "report.md"
        path.write_text(render_markdown(report), encoding="utf-8")
        written.append(path)
    if output_format in {"json", "both"}:
        path = output_dir / "report.json"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        written.append(path)
    return written
