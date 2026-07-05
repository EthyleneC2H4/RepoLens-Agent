"""Safe parsers for supported project manifest files."""

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from hello_agents.tools.base import Tool, ToolParameter
from hello_agents.tools.errors import ToolErrorCode
from hello_agents.tools.response import ToolResponse

from repolens.tools.paths import resolve_within_root


SUPPORTED_MANIFESTS = {
    "pyproject.toml": "python",
    "package.json": "node",
    "go.mod": "go",
}


class ParseManifestTool(Tool):
    """Parse known manifest formats without executing project code."""

    def __init__(self, project_root: str | Path, *, max_file_bytes: int = 1_000_000) -> None:
        super().__init__(
            name="parse_manifest",
            description="Parse a supported project manifest without executing it",
        )
        self.project_root = Path(project_root).expanduser().resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"repository root is not a directory: {self.project_root}")
        self.max_file_bytes = max_file_bytes

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Repository-relative manifest path",
                required=True,
            )
        ]

    def run(self, parameters: dict[str, Any]) -> ToolResponse:
        relative_path = parameters.get("path")
        if not isinstance(relative_path, str) or not relative_path.strip():
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_PARAM,
                message="path is required",
            )

        raw_candidate = self.project_root / relative_path
        if raw_candidate.is_symlink():
            return ToolResponse.error(
                code=ToolErrorCode.ACCESS_DENIED,
                message="manifest symlinks are not allowed",
            )

        try:
            candidate = resolve_within_root(self.project_root, relative_path)
        except ValueError as exc:
            return ToolResponse.error(
                code=ToolErrorCode.ACCESS_DENIED,
                message=str(exc),
            )

        manifest_type = SUPPORTED_MANIFESTS.get(candidate.name)
        if manifest_type is None:
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_FORMAT,
                message=f"unsupported manifest: {candidate.name}",
            )
        if not candidate.is_file():
            return ToolResponse.error(
                code=ToolErrorCode.NOT_FOUND,
                message=f"manifest not found: {relative_path}",
            )
        if candidate.stat().st_size > self.max_file_bytes:
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_FORMAT,
                message=f"manifest exceeds {self.max_file_bytes} bytes",
            )

        try:
            if manifest_type == "python":
                parsed = self._parse_pyproject(candidate)
            elif manifest_type == "node":
                parsed = self._parse_package_json(candidate)
            else:
                parsed = self._parse_go_mod(candidate)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, ValueError) as exc:
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_FORMAT,
                message=f"failed to parse {relative_path}: {exc}",
            )

        data = {
            "path": Path(relative_path).as_posix(),
            "manifest_type": manifest_type,
            **parsed,
        }
        return ToolResponse.success(text=json.dumps(data, ensure_ascii=False), data=data)

    @staticmethod
    def _parse_pyproject(path: Path) -> dict[str, Any]:
        with path.open("rb") as handle:
            document = tomllib.load(handle)

        project = document.get("project", {})
        poetry = document.get("tool", {}).get("poetry", {})
        dependencies = project.get("dependencies", [])
        if not dependencies and isinstance(poetry.get("dependencies"), dict):
            dependencies = [
                f"{name}{constraint if isinstance(constraint, str) else ''}"
                for name, constraint in poetry["dependencies"].items()
                if name.lower() != "python"
            ]

        return {
            "name": project.get("name") or poetry.get("name"),
            "version": project.get("version") or poetry.get("version"),
            "requires_python": project.get("requires-python")
            or poetry.get("dependencies", {}).get("python"),
            "dependencies": sorted(str(item) for item in dependencies),
            "optional_dependencies": project.get("optional-dependencies", {}),
            "scripts": project.get("scripts", {}),
            "build_backend": document.get("build-system", {}).get("build-backend"),
        }

    @staticmethod
    def _parse_package_json(path: Path) -> dict[str, Any]:
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
        if not isinstance(document, dict):
            raise ValueError("package.json must contain a JSON object")

        return {
            "name": document.get("name"),
            "version": document.get("version"),
            "package_manager": document.get("packageManager"),
            "engines": document.get("engines", {}),
            "scripts": document.get("scripts", {}),
            "dependencies": document.get("dependencies", {}),
            "dev_dependencies": document.get("devDependencies", {}),
        }

    @staticmethod
    def _parse_go_mod(path: Path) -> dict[str, Any]:
        module: str | None = None
        go_version: str | None = None
        dependencies: list[dict[str, Any]] = []
        in_require_block = False

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue
            if line.startswith("module "):
                module = line.split(maxsplit=1)[1]
                continue
            if line.startswith("go "):
                go_version = line.split(maxsplit=1)[1]
                continue
            if line == "require (":
                in_require_block = True
                continue
            if in_require_block and line == ")":
                in_require_block = False
                continue

            match = re.match(r"^(?:require\s+)?([^\s]+)\s+([^\s]+)(?:\s+//\s*(.*))?$", line)
            if match and (in_require_block or line.startswith("require ")):
                dependencies.append(
                    {
                        "module": match.group(1),
                        "version": match.group(2),
                        "indirect": match.group(3) == "indirect",
                    }
                )

        if module is None:
            raise ValueError("go.mod does not declare a module")
        return {
            "name": module,
            "version": None,
            "go_version": go_version,
            "dependencies": sorted(dependencies, key=lambda item: item["module"]),
        }
