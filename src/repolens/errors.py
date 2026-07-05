"""Structured failures exposed by the RepoLens workflow."""

from enum import StrEnum


class AnalysisErrorCode(StrEnum):
    CONFIGURATION = "CONFIGURATION_ERROR"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    TOKEN_BUDGET_EXCEEDED = "TOKEN_BUDGET_EXCEEDED"
    TOOL_ERROR = "TOOL_ERROR"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    EVIDENCE_INVALID = "EVIDENCE_INVALID"
    INTERNAL = "INTERNAL_ERROR"


class AnalysisError(RuntimeError):
    def __init__(self, code: AnalysisErrorCode, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code.value, "message": str(self), "retryable": self.retryable}
