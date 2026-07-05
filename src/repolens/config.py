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
