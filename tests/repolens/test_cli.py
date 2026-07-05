import json
from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app


runner = CliRunner()


def test_analyze_writes_markdown_and_json(tmp_path: Path) -> None:
    project = tmp_path / "project"
    output = tmp_path / "out"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "cli-sample"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (project / "README.md").write_text("# CLI Sample\n", encoding="utf-8")

    result = runner.invoke(app, ["analyze", str(project), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert (output / "report.md").is_file()
    document = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert document["metadata"]["mode"] == "fast"
    assert document["project_summary"].startswith("cli-sample contains")


def test_standard_mode_is_explicitly_deferred(tmp_path: Path) -> None:
    result = runner.invoke(app, ["analyze", str(tmp_path), "--mode", "standard"])
    assert result.exit_code == 2
    assert "planned for week 2" in result.output


def test_invalid_path_returns_usage_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["analyze", str(tmp_path / "missing")])
    assert result.exit_code == 2
    assert "does not exist" in result.output
