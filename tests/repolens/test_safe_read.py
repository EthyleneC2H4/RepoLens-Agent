from pathlib import Path

import pytest

from hello_agents.tools.response import ToolStatus
from repolens.tools.read import SafeReadTool


def test_safe_read_returns_numbered_content(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("first\nsecond\n", encoding="utf-8")
    response = SafeReadTool(tmp_path).run({"path": "app.py", "offset": 0, "limit": 2})
    assert response.status is ToolStatus.SUCCESS
    assert "1: first" in response.text
    assert "2: second" in response.text


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd"])
def test_safe_read_rejects_escape(tmp_path: Path, path: str) -> None:
    response = SafeReadTool(tmp_path).run({"path": path})
    assert response.status is ToolStatus.ERROR
