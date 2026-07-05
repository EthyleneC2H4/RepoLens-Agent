"""Safe deterministic repository tree scanner."""

import os
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from hello_agents.tools.base import Tool, ToolParameter
from hello_agents.tools.errors import ToolErrorCode
from hello_agents.tools.response import ToolResponse

from repolens.config import DEFAULT_IGNORE_PATTERNS
from repolens.tools.paths import should_ignore


class ScanRepoTool(Tool):
    """List repository metadata without reading file contents."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_depth: int = 4,
        max_files: int = 5_000,
        ignore_patterns: tuple[str, ...] = DEFAULT_IGNORE_PATTERNS,
    ) -> None:
        super().__init__(
            name="scan_repo",
            description="Scan a repository tree without reading file contents",
        )
        self.project_root = Path(project_root).expanduser().resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"repository root is not a directory: {self.project_root}")
        self.max_depth = max_depth
        self.max_files = max_files
        self.ignore_patterns = ignore_patterns

    def get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="max_depth",
                type="integer",
                description="Maximum directory depth to scan",
                required=False,
                default=self.max_depth,
            ),
            ToolParameter(
                name="max_files",
                type="integer",
                description="Maximum number of files to return",
                required=False,
                default=self.max_files,
            ),
        ]

    def run(self, parameters: dict[str, Any]) -> ToolResponse:
        try:
            max_depth = int(parameters.get("max_depth", self.max_depth))
            max_files = int(parameters.get("max_files", self.max_files))
        except (TypeError, ValueError):
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_PARAM,
                message="max_depth and max_files must be integers",
            )

        if not 1 <= max_depth <= 20 or not 1 <= max_files <= 100_000:
            return ToolResponse.error(
                code=ToolErrorCode.INVALID_PARAM,
                message="max_depth must be 1..20 and max_files must be 1..100000",
            )

        entries: list[dict[str, Any]] = []
        extension_counts: Counter[str] = Counter()
        directory_count = 0
        file_count = 0
        ignored_count = 0
        skipped_symlinks = 0
        truncated = False

        for current, dir_names, file_names in os.walk(
            self.project_root, topdown=True, followlinks=False
        ):
            current_path = Path(current)
            relative_current = current_path.relative_to(self.project_root)
            current_depth = len(relative_current.parts)

            safe_dirs: list[str] = []
            for name in sorted(dir_names):
                path = current_path / name
                relative = PurePosixPath(*path.relative_to(self.project_root).parts)
                if path.is_symlink():
                    skipped_symlinks += 1
                elif should_ignore(relative, self.ignore_patterns):
                    ignored_count += 1
                else:
                    safe_dirs.append(name)
            dir_names[:] = safe_dirs if current_depth < max_depth else []

            if current_depth > 0:
                directory_count += 1
                entries.append(
                    {"path": PurePosixPath(*relative_current.parts).as_posix(), "type": "directory"}
                )

            for name in sorted(file_names):
                path = current_path / name
                relative_path = path.relative_to(self.project_root)
                relative = PurePosixPath(*relative_path.parts)
                if path.is_symlink():
                    skipped_symlinks += 1
                    continue
                if should_ignore(relative, self.ignore_patterns):
                    ignored_count += 1
                    continue
                if file_count >= max_files:
                    truncated = True
                    dir_names[:] = []
                    break

                try:
                    size = path.stat().st_size
                except OSError:
                    ignored_count += 1
                    continue

                suffix = path.suffix.lower() or "[no extension]"
                extension_counts[suffix] += 1
                file_count += 1
                entries.append(
                    {
                        "path": relative.as_posix(),
                        "type": "file",
                        "size_bytes": size,
                        "extension": suffix,
                    }
                )

            if truncated:
                break

        entries.sort(key=lambda item: (item["path"], item["type"]))
        data = {
            "root_name": self.project_root.name,
            "files": file_count,
            "directories": directory_count,
            "entries": entries,
            "extensions": dict(sorted(extension_counts.items())),
            "ignored": ignored_count,
            "skipped_symlinks": skipped_symlinks,
            "truncated": truncated,
        }
        return ToolResponse.success(
            text=f"Scanned {file_count} files and {directory_count} directories",
            data=data,
        )
