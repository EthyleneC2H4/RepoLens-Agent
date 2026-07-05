"""Repository-confined adapter around HelloAgents ReadTool."""

from pathlib import Path
from typing import Any

from hello_agents.tools.builtin import ReadTool
from hello_agents.tools.errors import ToolErrorCode
from hello_agents.tools.response import ToolResponse, ToolStatus

from repolens.tools.paths import resolve_within_root


class SafeReadTool(ReadTool):
    """Read text files only from the configured repository root."""

    def __init__(self, project_root: str | Path, *, max_file_bytes: int = 1_000_000) -> None:
        super().__init__(project_root=str(project_root))
        self.name = "Read"
        self.max_file_bytes = max_file_bytes

    def _resolve_path(self, path: str) -> Path:
        return resolve_within_root(self.project_root, path)

    def run(self, parameters: dict[str, Any]) -> ToolResponse:
        path = parameters.get("path")
        if not isinstance(path, str) or not path.strip():
            return ToolResponse.error(ToolErrorCode.INVALID_PARAM, "path is required")
        try:
            resolved = self._resolve_path(path)
        except ValueError as exc:
            return ToolResponse.error(ToolErrorCode.ACCESS_DENIED, str(exc))
        if resolved.is_symlink():
            return ToolResponse.error(ToolErrorCode.ACCESS_DENIED, "file symlinks are not allowed")
        if resolved.is_file() and resolved.stat().st_size > self.max_file_bytes:
            return ToolResponse.error(
                ToolErrorCode.INVALID_FORMAT,
                f"file exceeds {self.max_file_bytes} bytes",
            )
        response = super().run(parameters)
        if response.status is ToolStatus.SUCCESS and "content" in response.data:
            offset = int(response.data.get("offset", 0))
            content = response.data["content"]
            numbered = "\n".join(
                f"{offset + index}: {line}" for index, line in enumerate(content.splitlines(), 1)
            )
            response.text = f"{response.text}\n{numbered}"
        return response
