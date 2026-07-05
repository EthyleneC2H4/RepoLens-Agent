"""Read-only code search backed by ripgrep without shell execution."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from hello_agents.tools.base import Tool, ToolParameter
from hello_agents.tools.errors import ToolErrorCode
from hello_agents.tools.response import ToolResponse


class SearchCodeTool(Tool):
    def __init__(
        self,
        project_root: str | Path,
        *,
        max_results: int = 50,
        timeout_seconds: float = 10.0,
        snippet_chars: int = 300,
    ) -> None:
        super().__init__(name="search_code", description="Search repository text with ripgrep")
        self.project_root = Path(project_root).expanduser().resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"repository root is not a directory: {self.project_root}")
        self.max_results = max_results
        self.timeout_seconds = timeout_seconds
        self.snippet_chars = snippet_chars

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="pattern", type="string", description="Regex or literal search pattern", required=True),
            ToolParameter(name="glob", type="string", description="Optional file glob such as *.py", required=False),
            ToolParameter(name="max_results", type="integer", description="Maximum matches", required=False, default=self.max_results),
        ]

    def run(self, parameters: dict[str, Any]) -> ToolResponse:
        pattern = parameters.get("pattern")
        glob = parameters.get("glob")
        try:
            max_results = int(parameters.get("max_results", self.max_results))
        except (TypeError, ValueError):
            return ToolResponse.error(ToolErrorCode.INVALID_PARAM, "max_results must be an integer")
        if not isinstance(pattern, str) or not pattern or len(pattern) > 500 or "\x00" in pattern:
            return ToolResponse.error(ToolErrorCode.INVALID_PARAM, "pattern must contain 1..500 characters")
        if glob is not None and (not isinstance(glob, str) or "\x00" in glob or len(glob) > 200):
            return ToolResponse.error(ToolErrorCode.INVALID_PARAM, "glob must be a string of at most 200 characters")
        if not 1 <= max_results <= 500:
            return ToolResponse.error(ToolErrorCode.INVALID_PARAM, "max_results must be 1..500")
        executable = shutil.which("rg")
        if executable is None:
            return ToolResponse.error(ToolErrorCode.NOT_FOUND, "ripgrep (rg) is required")

        command = [executable, "--json", "--hidden", "--glob", "!.git/**"]
        if glob:
            command.extend(["--glob", glob])
        command.extend(["--", pattern, "."])
        try:
            process = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResponse.error(ToolErrorCode.TIMEOUT, "code search timed out")
        if process.returncode not in {0, 1}:
            message = process.stderr.strip() or "ripgrep failed"
            return ToolResponse.error(ToolErrorCode.EXECUTION_ERROR, message[:500])

        matches: list[dict[str, Any]] = []
        for raw_line in process.stdout.splitlines():
            event = json.loads(raw_line)
            if event.get("type") != "match":
                continue
            data = event["data"]
            path = data["path"]["text"].removeprefix("./")
            line_number = int(data["line_number"])
            snippet = data["lines"]["text"].strip().replace("\x00", "")[: self.snippet_chars]
            matches.append({"path": path, "line": line_number, "snippet": snippet})
            if len(matches) >= max_results:
                break
        preview = "\n".join(
            f"{item['path']}:{item['line']}: {item['snippet']}" for item in matches
        ) or "No matches found."
        return ToolResponse.success(
            text=f"Found {len(matches)} matches.\n{preview}",
            data={"matches": matches, "count": len(matches), "truncated": len(matches) >= max_results},
        )
