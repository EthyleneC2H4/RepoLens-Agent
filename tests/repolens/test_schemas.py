from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from repolens.config import RepoLensConfig
from repolens.schemas import AnalysisMetadata, AnalysisReport, EvidenceRef


def test_config_resolves_repository_root(tmp_path: Path) -> None:
    config = RepoLensConfig(root=tmp_path)

    assert config.root == tmp_path.resolve()
    assert config.mode == "fast"
    assert ".git" in config.ignore_patterns


def test_config_rejects_missing_repository(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="does not exist"):
        RepoLensConfig(root=tmp_path / "missing")


@pytest.mark.parametrize("path", ["/etc/passwd", "../secret", ".", ""])
def test_evidence_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        EvidenceRef(path=path, claim="unsafe")


def test_evidence_normalizes_windows_separators() -> None:
    evidence = EvidenceRef(path=r"src\repolens\cli.py", claim="CLI entry point")

    assert evidence.path == "src/repolens/cli.py"


def test_report_round_trip_json() -> None:
    report = AnalysisReport(
        project_summary="A deterministic repository analyzer.",
        evidence=[EvidenceRef(path="pyproject.toml", claim="Python project metadata")],
        metadata=AnalysisMetadata(
            mode="fast",
            source_root="/tmp/project",
            generated_at=datetime(2026, 7, 5, tzinfo=UTC),
            duration_ms=10,
            files_scanned=5,
            directories_scanned=2,
            manifests_parsed=1,
        ),
    )

    restored = AnalysisReport.model_validate_json(report.model_dump_json())

    assert restored == report
