"""Shared token accounting wrapper for HelloAgents-compatible LLMs."""

from dataclasses import dataclass
from typing import Any

from repolens.errors import AnalysisError, AnalysisErrorCode


@dataclass
class TokenBudget:
    limit: int
    used: int = 0
    calls: int = 0

    def record(self, response: Any) -> None:
        usage = getattr(response, "usage", None) or {}
        self.used += int(usage.get("total_tokens", 0))
        self.calls += 1
        if self.used > self.limit:
            raise AnalysisError(
                AnalysisErrorCode.TOKEN_BUDGET_EXCEEDED,
                f"analysis used {self.used} tokens, exceeding the {self.limit} token budget",
            )

    def ensure_available(self) -> None:
        if self.used >= self.limit:
            raise AnalysisError(
                AnalysisErrorCode.TOKEN_BUDGET_EXCEEDED,
                f"analysis exhausted its {self.limit} token budget",
            )


class BudgetedLLM:
    """Delegate to an LLM while sharing one budget across all agents."""

    def __init__(self, llm: Any, budget: TokenBudget) -> None:
        self._llm = llm
        self.budget = budget
        self.model = llm.model

    def invoke_with_tools(self, *args: Any, **kwargs: Any) -> Any:
        self.budget.ensure_available()
        response = self._llm.invoke_with_tools(*args, **kwargs)
        self.budget.record(response)
        return response

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        self.budget.ensure_available()
        response = self._llm.invoke(*args, **kwargs)
        self.budget.record(response)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._llm, name)
