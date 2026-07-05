"""Architecture and runtime analysis roles with isolated contexts."""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from hello_agents.tools.tool_filter import ReadOnlyFilter
from pydantic import BaseModel

from repolens.agent_findings import ArchitectureFindings, RuntimeFindings, parse_findings
from repolens.orchestrator import ORCHESTRATOR_PROMPT, RepositoryOrchestrator


ARCHITECTURE_PROMPT = ORCHESTRATOR_PROMPT + """
Role: architecture analyst. Inspect source entry points, top-level modules, and concrete call flows.
Use search_code and Read before claiming source behavior. Return only JSON matching this schema:
{schema}
"""

RUNTIME_PROMPT = ORCHESTRATOR_PROMPT + """
Role: test and runtime analyst. Inspect manifests, README, tests, and executable entry points.
Only report commands literally supported by files. Return only JSON matching this schema:
{schema}
"""

FindingsT = TypeVar("FindingsT", bound=BaseModel)


@dataclass
class SubagentSummary(Generic[FindingsT]):
    role: str
    findings: FindingsT
    metadata: dict[str, Any]


class AnalysisSubagents:
    """Run isolated role agents and expose only validated summaries."""

    def __init__(self, orchestrator: RepositoryOrchestrator) -> None:
        self.orchestrator = orchestrator
        self.filter = ReadOnlyFilter(
            additional_allowed=["scan_repo", "search_code", "parse_manifest"]
        )

    def run_architecture(self) -> SubagentSummary[ArchitectureFindings]:
        return self._run(
            role="architecture",
            prompt=ARCHITECTURE_PROMPT.format(
                schema=ArchitectureFindings.model_json_schema()
            ),
            task=(
                "Analyze repository architecture. Find actual entry points, module responsibilities, "
                "and at most three evidence-backed call flows. Return the required JSON only."
            ),
            model=ArchitectureFindings,
        )

    def run_runtime(self) -> SubagentSummary[RuntimeFindings]:
        return self._run(
            role="runtime",
            prompt=RUNTIME_PROMPT.format(schema=RuntimeFindings.model_json_schema()),
            task=(
                "Analyze installation, run, and test commands plus a recommended file reading order. "
                "Every command needs file evidence. Return the required JSON only."
            ),
            model=RuntimeFindings,
        )

    def _run(
        self,
        *,
        role: str,
        prompt: str,
        task: str,
        model: type[FindingsT],
    ) -> SubagentSummary[FindingsT]:
        agent = self.orchestrator.create_agent(f"repolens-{role}", prompt)
        result = agent.run_as_subagent(
            task=task,
            tool_filter=self.filter,
            return_summary=False,
            max_steps_override=self.orchestrator.config.subagent_max_steps,
        )
        if not result["success"]:
            from repolens.errors import AnalysisError, AnalysisErrorCode

            raise AnalysisError(
                AnalysisErrorCode.MODEL_UNAVAILABLE,
                str(result["metadata"].get("error", "subagent failed")),
                retryable=True,
            )
        findings = parse_findings(result["result"], model)
        return SubagentSummary(role=role, findings=findings, metadata=result["metadata"])
