import json
from pathlib import Path

import pytest

from hello_agents.core.llm_response import LLMToolResponse

from repolens.config import RepoLensConfig
from repolens.errors import AnalysisError, AnalysisErrorCode
from repolens.orchestrator import RepositoryOrchestrator


class ScriptedLLM:
    model = "mock"

    def __init__(self, contents):
        self.contents = iter(contents)

    def invoke_with_tools(self, **_kwargs):
        return LLMToolResponse(
            content=next(self.contents),
            tool_calls=[],
            model="mock",
            usage={"total_tokens": 5},
        )


class ExplodingLLM:
    model = "should-not-run"

    def invoke_with_tools(self, **_kwargs):
        raise AssertionError("resumed stages must not call the model")


class TimeoutLLM:
    model = "timeout"

    def invoke_with_tools(self, **_kwargs):
        raise TimeoutError("api_key=super-secret /Users/ethylene/private")


def test_trace_session_and_resume(tmp_path: Path) -> None:
    project = tmp_path / "project"
    output = tmp_path / "output"
    project.mkdir()
    (project / "README.md").write_text("sample\n", encoding="utf-8")
    first = RepositoryOrchestrator(
        RepoLensConfig(root=project, mode="standard", output_dir=output),
        llm=ScriptedLLM([json.dumps({}), json.dumps({"reading_path": ["README.md"]})]),
    )
    report = first.analyze()

    assert report.reading_path == ["README.md"]
    assert first.trace_path and first.trace_path.is_file()
    assert first.session_path and Path(first.session_path).is_file()
    trace = first.trace_path.read_text(encoding="utf-8")
    assert "analysis_complete" in trace
    session = json.loads(Path(first.session_path).read_text(encoding="utf-8"))
    assert set(session["metadata"]["completed"]) == {"architecture", "runtime"}

    resumed = RepositoryOrchestrator(
        RepoLensConfig(
            root=project,
            mode="standard",
            output_dir=tmp_path / "resumed",
            resume_session=Path(first.session_path),
        ),
        llm=ExplodingLLM(),
    ).analyze()
    assert resumed.reading_path == ["README.md"]
    assert resumed.metadata.tokens == 10


def test_model_timeout_is_structured_and_trace_is_sanitized(tmp_path: Path) -> None:
    output = tmp_path / "output"
    orchestrator = RepositoryOrchestrator(
        RepoLensConfig(root=tmp_path, mode="standard", output_dir=output),
        llm=TimeoutLLM(),
    )
    with pytest.raises(AnalysisError) as exc:
        orchestrator.analyze()
    assert exc.value.code is AnalysisErrorCode.MODEL_TIMEOUT
    trace = orchestrator.trace_path.read_text(encoding="utf-8")
    assert "super-secret" not in trace
    assert "/Users/ethylene" not in trace
    assert "MODEL_TIMEOUT" in trace or "AnalysisError" in trace
