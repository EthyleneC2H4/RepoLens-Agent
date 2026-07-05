from datetime import datetime, timezone
from pathlib import Path

from repolens.analyzer import FastAnalyzer
from repolens.config import RepoLensConfig


def _fixture(root: Path) -> None:
    (root / "src" / "sample").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "README.md").write_text("# Sample\n", encoding="utf-8")
    (root / "src" / "sample" / "cli.py").write_text("def app(): ...\n", encoding="utf-8")
    (root / "tests" / "test_cli.py").write_text("def test_ok(): ...\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n'
        '[project.scripts]\nsample = "sample.cli:app"\n',
        encoding="utf-8",
    )


def test_fast_analyzer_builds_evidence_backed_report(tmp_path: Path) -> None:
    _fixture(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    report = FastAnalyzer(RepoLensConfig(root=tmp_path), clock=lambda: now).analyze()

    assert report.project_summary.startswith("sample contains")
    assert report.tech_stack[0].name == "Python"
    assert report.entry_points[0].path == "src/sample/cli.py"
    assert any(item.command == "sample" for item in report.run_commands)
    assert any(item.command == "python -m pytest" for item in report.run_commands)
    assert report.evidence[0].path == "pyproject.toml"
    assert report.metadata.generated_at == now


def test_fast_analysis_lists_are_deterministic(tmp_path: Path) -> None:
    _fixture(tmp_path)
    config = RepoLensConfig(root=tmp_path)
    first = FastAnalyzer(config).analyze().model_dump(exclude={"metadata"})
    second = FastAnalyzer(config).analyze().model_dump(exclude={"metadata"})
    assert first == second
