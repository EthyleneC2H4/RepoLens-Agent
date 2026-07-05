"""Stable Markdown and JSON output for analysis reports."""

from pathlib import Path

from repolens.schemas import AnalysisReport


def render_markdown(report: AnalysisReport) -> str:
    lines = ["# RepoLens Analysis Report", "", report.project_summary, ""]
    sections = [
        ("Technology Stack", [f"- **{x.name}** ({x.category})" + (f": {x.version}" if x.version else "") for x in report.tech_stack]),
        ("Entry Points", [f"- `{x.path}` — {x.description}" for x in report.entry_points]),
        ("Module Map", [f"- `{x.path}/` — {x.purpose}" for x in report.module_map]),
        ("Call Flows", [f"- **{x.name}:** " + " → ".join(x.steps) for x in report.call_flows]),
        ("Run Commands", [f"- `{x.command}` — {x.purpose}" for x in report.run_commands]),
        ("Risks", [f"- **{x.level.upper()}** — {x.description}" for x in report.risks]),
        ("Recommended Reading Order", [f"{index}. `{path}`" for index, path in enumerate(report.reading_path, 1)]),
        ("File Evidence", [f"- `{x.path}` — {x.claim}" for x in report.evidence]),
    ]
    for heading, items in sections:
        lines.extend([f"## {heading}", "", *(items or ["_No items detected._"]), ""])
    metadata = report.metadata
    lines.extend(
        [
            "## Analysis Metadata",
            "",
            f"- Mode: `{metadata.mode}`",
            f"- Files scanned: {metadata.files_scanned}",
            f"- Directories scanned: {metadata.directories_scanned}",
            f"- Manifests parsed: {metadata.manifests_parsed}",
            f"- Generated at: {metadata.generated_at.isoformat()}",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: AnalysisReport, output_dir: Path, output_format: str) -> list[Path]:
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
