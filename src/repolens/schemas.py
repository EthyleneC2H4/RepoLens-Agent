"""Structured report schema used by deterministic and agentic analysis."""

from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EvidenceRef(BaseModel):
    """A claim grounded in a repository-relative file location."""

    path: str
    claim: str
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)

    @field_validator("path")
    @classmethod
    def require_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/").strip()
        path = PurePosixPath(normalized)
        if not normalized or normalized == "." or path.is_absolute() or ".." in path.parts:
            raise ValueError("evidence path must be a safe repository-relative path")
        return path.as_posix()

    @model_validator(mode="after")
    def validate_line_range(self) -> "EvidenceRef":
        if self.line_end is not None and self.line_start is None:
            raise ValueError("line_end requires line_start")
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError("line_end must be greater than or equal to line_start")
        return self


class TechStackItem(BaseModel):
    category: str
    name: str
    version: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class EntryPoint(BaseModel):
    path: str
    kind: str
    description: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ModuleInfo(BaseModel):
    path: str
    purpose: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class CallFlow(BaseModel):
    name: str
    steps: list[str]
    evidence: list[EvidenceRef] = Field(default_factory=list)


class RunCommand(BaseModel):
    command: str
    purpose: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class RiskItem(BaseModel):
    level: Literal["low", "medium", "high"]
    description: str
    evidence: list[EvidenceRef] = Field(default_factory=list)


class AnalysisMetadata(BaseModel):
    mode: Literal["fast", "standard"]
    model: str | None = None
    source_root: str
    generated_at: datetime
    duration_ms: int = Field(ge=0)
    files_scanned: int = Field(ge=0)
    directories_scanned: int = Field(ge=0)
    manifests_parsed: int = Field(ge=0)
    tokens: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)


class AnalysisReport(BaseModel):
    """Canonical RepoLens analysis report."""

    project_summary: str
    tech_stack: list[TechStackItem] = Field(default_factory=list)
    entry_points: list[EntryPoint] = Field(default_factory=list)
    module_map: list[ModuleInfo] = Field(default_factory=list)
    call_flows: list[CallFlow] = Field(default_factory=list)
    run_commands: list[RunCommand] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    reading_path: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    metadata: AnalysisMetadata
