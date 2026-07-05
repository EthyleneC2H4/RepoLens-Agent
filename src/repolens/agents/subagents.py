"""Architecture and runtime analysis roles with isolated contexts."""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from hello_agents.tools.tool_filter import ReadOnlyFilter
from pydantic import BaseModel

from repolens.agent_findings import ArchitectureFindings, RuntimeFindings, parse_role_findings
from repolens.errors import AnalysisError
from repolens.orchestrator import ORCHESTRATOR_PROMPT, RepositoryOrchestrator


ARCHITECTURE_PROMPT = ORCHESTRATOR_PROMPT + """
Role: architecture analyst. Inspect source entry points, top-level modules, and concrete call flows.
Use search_code and Read before claiming source behavior. Return only JSON matching this schema:
{schema}
Keep the JSON under 1500 characters. Omit findings you cannot verify. Do not repeat the schema.
Call scan_repo once, make at most three targeted follow-up tool calls, then call Finish.
"""

RUNTIME_PROMPT = ORCHESTRATOR_PROMPT + """
Role: test and runtime analyst. Inspect manifests, README, tests, and executable entry points.
Only report commands literally supported by files. Return only JSON matching this schema:
{schema}
Keep the JSON under 1200 characters. Omit findings you cannot verify. Do not repeat the schema.
Call scan_repo once, make at most three targeted follow-up tool calls, then call Finish.
"""

ARCHITECTURE_CONTRACT = """{"findings":[{"type":"entry_point|module|call_flow|risk","title":"file path or finding name","description":"short fact","evidence":{"path":"file","claim":"support","line_start":1,"line_end":2},"value":"kind, risk level, or steps joined by ->"}]}"""

RUNTIME_CONTRACT = """{"findings":[{"type":"run_command|risk|reading_path","title":"command or file path","description":"short fact","evidence":{"path":"file","claim":"support","line_start":1},"value":"risk level or null"}]}"""

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
            prompt=ARCHITECTURE_PROMPT.format(schema=ARCHITECTURE_CONTRACT),
            task=(
                "Analyze repository architecture. Find actual entry points, module responsibilities, "
                "and at most three evidence-backed call flows. Return the required JSON only."
            ),
            model=ArchitectureFindings,
        )

    def run_runtime(self) -> SubagentSummary[RuntimeFindings]:
        return self._run(
            role="runtime",
            prompt=RUNTIME_PROMPT.format(schema=RUNTIME_CONTRACT),
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
        if self.orchestrator.llm.last_error:
            raise self.orchestrator.llm.last_error
        if not result["success"]:
            from repolens.errors import AnalysisErrorCode

            raise AnalysisError(
                AnalysisErrorCode.MODEL_UNAVAILABLE,
                str(result["metadata"].get("error", "subagent failed")),
                retryable=True,
            )
        try:
            findings = parse_role_findings(result["result"], role)
        except AnalysisError:
            observations = getattr(agent.tool_registry, "observations", [])
            if not observations:
                raise
            contract = ARCHITECTURE_CONTRACT if role == "architecture" else RUNTIME_CONTRACT
            synthesis = self.orchestrator.llm.invoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "Convert only the supplied read-only tool observations into the JSON contract. "
                            "Do not add unsupported facts. Return JSON only. Contract: " + contract
                        ),
                    },
                    {"role": "user", "content": str(observations)},
                ],
                temperature=0,
            )
            findings = parse_role_findings(synthesis.content, role)
        result["metadata"]["tool_calls"] = getattr(agent.tool_registry, "tool_calls", 0)
        return SubagentSummary(role=role, findings=findings, metadata=result["metadata"])
