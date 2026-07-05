"""Strict outputs accepted from read-only analysis subagents."""

import json
import re
from typing import TypeVar

from pydantic import BaseModel, Field, ValidationError

from repolens.errors import AnalysisError, AnalysisErrorCode
from repolens.schemas import CallFlow, EntryPoint, ModuleInfo, RiskItem, RunCommand


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
