from datetime import datetime, timezone
from pathlib import Path

import pytest

from repolens.errors import AnalysisError, AnalysisErrorCode
from repolens.renderers import render_markdown, write_report
from repolens.schemas import AnalysisMetadata, AnalysisReport, EntryPoint, EvidenceRef


def _report(root: Path, *, grounded: bool = True) -> AnalysisReport:
    evidence = [EvidenceRef(path="app.py", claim="entry", line_start=1)] if grounded else []
    return AnalysisReport(
        project_summary="sample project",
        entry_points=[EntryPoint(path="app.py", kind="application", description="entry", evidence=evidence)],
        metadata=AnalysisMetadata(
            mode="standard",
            model="mock",
            source_root=str(root),
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            duration_ms=5,
            files_scanned=1,
            directories_scanned=0,
            manifests_parsed=0,
            tokens=10,
            tool_calls=2,
        ),
    )


def test_markdown_shows_evidence_unknowns_and_metrics(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("pass\n", encoding="utf-8")
    markdown = render_markdown(_report(tmp_path))
    assert "Evidence: `app.py:1`" in markdown
    assert "_Unknown — no verified evidence._" in markdown
    assert "Model tokens: 10" in markdown


def test_writer_refuses_ungrounded_standard_report(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("pass\n", encoding="utf-8")
    with pytest.raises(AnalysisError) as exc:
        write_report(_report(tmp_path, grounded=False), tmp_path / "out", "both")
    assert exc.value.code is AnalysisErrorCode.EVIDENCE_INVALID
    assert not (tmp_path / "out" / "report.json").exists()
