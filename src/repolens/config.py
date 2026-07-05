"""Configuration models for deterministic repository analysis."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


DEFAULT_IGNORE_PATTERNS = (
    ".git",
    ".env",
    ".env.local",
    ".env.*.local",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "*.egg-info",
)


class RepoLensConfig(BaseModel):
    """Validated options shared by the scanner, analyzer, and CLI."""

    root: Path
    output_dir: Path | None = None
    mode: Literal["fast", "standard"] = "fast"
    output_format: Literal["md", "json", "both"] = "both"
    max_depth: int = Field(default=4, ge=1, le=20)
    max_files: int = Field(default=5_000, ge=1, le=100_000)
    max_file_bytes: int = Field(default=1_000_000, ge=1)
    agent_max_steps: int = Field(default=6, ge=1, le=20)
    subagent_max_steps: int = Field(default=4, ge=1, le=15)
    token_budget: int = Field(default=12_000, ge=256, le=1_000_000)
    context_window: int = Field(default=16_000, ge=1_024)
    tool_output_max_lines: int = Field(default=200, ge=10, le=2_000)
    tool_output_max_bytes: int = Field(default=20_000, ge=1_024)
    trace_enabled: bool = True
    session_enabled: bool = True
    ignore_patterns: tuple[str, ...] = DEFAULT_IGNORE_PATTERNS

    @field_validator("root")
    @classmethod
    def validate_root(cls, value: Path) -> Path:
        root = value.expanduser().resolve()
        if not root.exists():
            raise ValueError(f"repository path does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"repository path is not a directory: {root}")
        return root

    @field_validator("output_dir")
    @classmethod
    def normalize_output_dir(cls, value: Path | None) -> Path | None:
        return value.expanduser().resolve() if value is not None else None
