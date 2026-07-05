"""Strict outputs accepted from read-only analysis subagents."""

import json
import re
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from repolens.errors import AnalysisError, AnalysisErrorCode
from repolens.schemas import CallFlow, EntryPoint, EvidenceRef, ModuleInfo, RiskItem, RunCommand


class FlatFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["entry_point", "module", "call_flow", "run_command", "risk", "reading_path"]
    title: str
    description: str = ""
    evidence: EvidenceRef | None = None
    value: str | list[str] | None = None


class FlatFindings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[FlatFinding] = Field(default_factory=list)

    def architecture(self) -> "ArchitectureFindings":
        entries, modules, flows, risks = [], [], [], []
        for item in self.findings:
            evidence = [item.evidence] if item.evidence else []
            if item.type == "entry_point":
                entries.append(EntryPoint(path=item.title, kind=str(item.value or "application"), description=item.description, evidence=evidence))
            elif item.type == "module":
                modules.append(ModuleInfo(path=item.title, purpose=item.description, evidence=evidence))
            elif item.type == "call_flow":
                steps = item.value if isinstance(item.value, list) else [part.strip() for part in str(item.value or "").split("->") if part.strip()]
                if steps:
                    flows.append(CallFlow(name=item.title, steps=steps, evidence=evidence))
            elif item.type == "risk" and str(item.value) in {"low", "medium", "high"}:
                risks.append(RiskItem(level=str(item.value), description=item.description, evidence=evidence))
        return ArchitectureFindings(entry_points=entries, module_map=modules, call_flows=flows, risks=risks)

    def runtime(self) -> "RuntimeFindings":
        commands, risks, reading = [], [], []
        for item in self.findings:
            evidence = [item.evidence] if item.evidence else []
            if item.type == "run_command":
                commands.append(RunCommand(command=item.title, purpose=item.description, evidence=evidence))
            elif item.type == "risk" and str(item.value) in {"low", "medium", "high"}:
                risks.append(RiskItem(level=str(item.value), description=item.description, evidence=evidence))
            elif item.type == "reading_path":
                reading.append(item.evidence.path if item.evidence else item.title)
        return RuntimeFindings(run_commands=commands, risks=risks, reading_path=reading)


class ArchitectureFindings(BaseModel):
    entry_points: list[EntryPoint] = Field(default_factory=list)
    module_map: list[ModuleInfo] = Field(default_factory=list)
    call_flows: list[CallFlow] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)


class RuntimeFindings(BaseModel):
    run_commands: list[RunCommand] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    reading_path: list[str] = Field(default_factory=list)


FindingModel = TypeVar("FindingModel", bound=BaseModel)


def parse_findings(text: str, model: type[FindingModel]) -> FindingModel:
    """Extract one JSON object, including common fenced model output."""
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    else:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    try:
        return model.model_validate(json.loads(candidate))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AnalysisError(
            AnalysisErrorCode.INVALID_MODEL_OUTPUT,
            f"subagent did not return valid {model.__name__} JSON: {exc}",
        ) from exc


def parse_role_findings(text: str, role: Literal["architecture", "runtime"]):
    """Prefer the small-model flat protocol, then accept the original schema."""
    try:
        flat = parse_findings(text, FlatFindings)
        return flat.architecture() if role == "architecture" else flat.runtime()
    except AnalysisError:
        model = ArchitectureFindings if role == "architecture" else RuntimeFindings
        return parse_findings(text, model)
