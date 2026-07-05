from pathlib import Path
from types import SimpleNamespace

import pytest

from repolens.config import RepoLensConfig
from repolens.errors import AnalysisError, AnalysisErrorCode
from repolens.llm_budget import BudgetedLLM, TokenBudget
from repolens.orchestrator import RepositoryOrchestrator
from repolens.toolset import build_readonly_registry


class FakeLLM:
    model = "fake-model"

    def invoke(self, *_args, **_kwargs):
        return SimpleNamespace(usage={"total_tokens": 6})


def test_readonly_registry_contains_only_expected_tools(tmp_path: Path) -> None:
    config = RepoLensConfig(root=tmp_path, mode="standard")
    registry = build_readonly_registry(config)
    assert registry.list_tools() == ["scan_repo", "parse_manifest", "Read", "search_code"]


def test_orchestrator_applies_agent_limits(tmp_path: Path) -> None:
    config = RepoLensConfig(root=tmp_path, mode="standard", agent_max_steps=3)
    orchestrator = RepositoryOrchestrator(config, llm=FakeLLM())
    agent = orchestrator.create_agent("test")
    assert agent.max_steps == 3
    assert agent.config.context_window == config.context_window
    assert agent.config.subagent_enabled is False


def test_shared_token_budget_fails_structurally() -> None:
    budget = TokenBudget(limit=10)
    llm = BudgetedLLM(FakeLLM(), budget)
    llm.invoke([])
    with pytest.raises(AnalysisError) as exc:
        llm.invoke([])
    assert exc.value.code is AnalysisErrorCode.TOKEN_BUDGET_EXCEEDED
