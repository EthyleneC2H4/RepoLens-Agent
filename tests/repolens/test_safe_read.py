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


def test_safe_read_caps_context_output(tmp_path: Path) -> None:
    (tmp_path / "large.txt").write_text("\n".join("x" * 100 for _ in range(50)), encoding="utf-8")
    response = SafeReadTool(
        tmp_path, max_output_lines=10, max_output_bytes=300
    ).run({"path": "large.txt", "limit": 2_000})
    assert response.status is ToolStatus.SUCCESS
    assert len(response.text.encode("utf-8")) < 350
    assert "output truncated" in response.text
