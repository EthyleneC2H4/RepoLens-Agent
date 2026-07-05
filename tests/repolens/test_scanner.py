from pathlib import Path

import pytest

from hello_agents.tools.response import ToolStatus
from repolens.tools.paths import resolve_within_root
from repolens.tools.scanner import ScanRepoTool


def _paths(response_data: dict) -> set[str]:
    return {entry["path"] for entry in response_data["entries"]}


def test_scanner_is_deterministic_and_ignores_runtime_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("SECRET=placeholder\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("private\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("dep\n", encoding="utf-8")

    tool = ScanRepoTool(tmp_path)
    first = tool.run({})
    second = tool.run({})

    assert first.status is ToolStatus.SUCCESS
    assert first.data == second.data
    paths = _paths(first.data)
    assert "src/app.py" in paths
    assert ".env.example" in paths
    assert ".env" not in paths
    assert ".git/config" not in paths
    assert "node_modules/dep.js" not in paths


def test_scanner_respects_max_depth(tmp_path: Path) -> None:
    nested = tmp_path / "one" / "two" / "three"
    nested.mkdir(parents=True)
    (nested / "deep.py").write_text("pass\n", encoding="utf-8")

    response = ScanRepoTool(tmp_path, max_depth=2).run({})

    assert "one/two/three/deep.py" not in _paths(response.data)


def test_scanner_skips_symlinks(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    link = tmp_path / "outside-link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are not available")

    response = ScanRepoTool(tmp_path).run({})

    assert "outside-link.txt" not in _paths(response.data)
    assert response.data["skipped_symlinks"] == 1


@pytest.mark.parametrize("unsafe", ["../secret", "/etc/passwd"])
def test_resolve_within_root_rejects_escape(tmp_path: Path, unsafe: str) -> None:
    with pytest.raises(ValueError):
        resolve_within_root(tmp_path, unsafe)


def test_resolve_within_root_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "outside"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available")

    with pytest.raises(ValueError, match="outside"):
        resolve_within_root(tmp_path, "outside/file.txt")
