import json
from pathlib import Path

import pytest

from hello_agents.tools.errors import ToolErrorCode
from hello_agents.tools.response import ToolStatus
from repolens.tools.manifest import ParseManifestTool


def test_parse_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[build-system]
build-backend = "setuptools.build_meta"

[project]
name = "sample-python"
version = "1.2.3"
requires-python = ">=3.11"
dependencies = ["requests>=2"]

[project.scripts]
sample = "sample.cli:app"
""".strip(),
        encoding="utf-8",
    )

    response = ParseManifestTool(tmp_path).run({"path": "pyproject.toml"})

    assert response.status is ToolStatus.SUCCESS
    assert response.data["manifest_type"] == "python"
    assert response.data["name"] == "sample-python"
    assert response.data["scripts"] == {"sample": "sample.cli:app"}


def test_parse_package_json(tmp_path: Path) -> None:
    document = {
        "name": "sample-node",
        "version": "2.0.0",
        "scripts": {"dev": "vite", "test": "vitest"},
        "dependencies": {"react": "^19.0.0"},
    }
    (tmp_path / "package.json").write_text(json.dumps(document), encoding="utf-8")

    response = ParseManifestTool(tmp_path).run({"path": "package.json"})

    assert response.status is ToolStatus.SUCCESS
    assert response.data["manifest_type"] == "node"
    assert response.data["scripts"]["dev"] == "vite"


def test_parse_go_mod(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text(
        """
module example.com/sample

go 1.23

require (
    github.com/acme/direct v1.2.0
    github.com/acme/indirect v0.5.0 // indirect
)
""".strip(),
        encoding="utf-8",
    )

    response = ParseManifestTool(tmp_path).run({"path": "go.mod"})

    assert response.status is ToolStatus.SUCCESS
    assert response.data["name"] == "example.com/sample"
    assert response.data["go_version"] == "1.23"
    assert response.data["dependencies"][1]["indirect"] is True


def test_reject_unsupported_manifest(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests\n", encoding="utf-8")

    response = ParseManifestTool(tmp_path).run({"path": "requirements.txt"})

    assert response.status is ToolStatus.ERROR
    assert response.error_info["code"] == ToolErrorCode.INVALID_FORMAT


def test_reject_malformed_manifest(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{bad json", encoding="utf-8")

    response = ParseManifestTool(tmp_path).run({"path": "package.json"})

    assert response.status is ToolStatus.ERROR
    assert response.error_info["code"] == ToolErrorCode.INVALID_FORMAT


@pytest.mark.parametrize("unsafe", ["../package.json", "/tmp/package.json"])
def test_reject_manifest_path_escape(tmp_path: Path, unsafe: str) -> None:
    response = ParseManifestTool(tmp_path).run({"path": unsafe})

    assert response.status is ToolStatus.ERROR
    assert response.error_info["code"] == ToolErrorCode.ACCESS_DENIED
