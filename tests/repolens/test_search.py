from pathlib import Path

from hello_agents.tools.response import ToolStatus
from repolens.tools.search import SearchCodeTool


def test_search_returns_relative_path_line_and_snippet(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main():\n    return 42\n", encoding="utf-8")
    response = SearchCodeTool(tmp_path).run({"pattern": "return", "glob": "*.py"})
    assert response.status is ToolStatus.SUCCESS
    assert response.data["matches"] == [
        {"path": "src/app.py", "line": 2, "snippet": "return 42"}
    ]
    assert "src/app.py:2" in response.text


def test_search_limits_results_and_does_not_interpret_shell(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("needle\nneedle\n", encoding="utf-8")
    response = SearchCodeTool(tmp_path).run({"pattern": "needle; touch PWNED", "max_results": 1})
    assert response.status is ToolStatus.SUCCESS
    assert not (tmp_path / "PWNED").exists()


def test_search_reports_bad_regex(tmp_path: Path) -> None:
    response = SearchCodeTool(tmp_path).run({"pattern": "["})
    assert response.status is ToolStatus.ERROR
