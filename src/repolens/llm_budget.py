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

    def __init__(self, llm: Any, budget: TokenBudget, *, reasoning_effort: str | None = None) -> None:
        self._llm = llm
        self.budget = budget
        self.model = llm.model
        self.last_error: AnalysisError | None = None
        self.reasoning_effort = reasoning_effort

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        self.budget.ensure_available()
        try:
            response = getattr(self._llm, method)(*args, **kwargs)
        except AnalysisError as exc:
            self.last_error = exc
            raise
        except (TimeoutError, ConnectionError) as exc:
            code = (
                AnalysisErrorCode.MODEL_TIMEOUT
                if isinstance(exc, TimeoutError)
                else AnalysisErrorCode.MODEL_UNAVAILABLE
            )
            self.last_error = AnalysisError(code, str(exc), retryable=True)
            raise self.last_error from exc
        except Exception as exc:
            self.last_error = AnalysisError(
                AnalysisErrorCode.MODEL_UNAVAILABLE, str(exc), retryable=True
            )
            raise self.last_error from exc
        try:
            self.budget.record(response)
        except AnalysisError as exc:
            self.last_error = exc
            raise
        return response

    def invoke_with_tools(self, *args: Any, **kwargs: Any) -> Any:
        if self.reasoning_effort and (
            "qwen" in self.model.lower() or "11434" in str(getattr(self._llm, "base_url", ""))
        ):
            kwargs.setdefault("reasoning_effort", self.reasoning_effort)
        return self._call("invoke_with_tools", *args, **kwargs)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        if self.reasoning_effort and (
            "qwen" in self.model.lower() or "11434" in str(getattr(self._llm, "base_url", ""))
        ):
            kwargs.setdefault("reasoning_effort", self.reasoning_effort)
        return self._call("invoke", *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._llm, name)
