import json
from pathlib import Path

from hello_agents.core.llm_response import LLMToolResponse, ToolCall

from repolens.config import RepoLensConfig
from repolens.evidence import EvidenceValidator
from repolens.orchestrator import RepositoryOrchestrator


class ScriptedLLM:
    model = "mock-tool-model"

    def __init__(self, responses, synthesis=None):
        self.responses = iter(responses)
        self.synthesis = iter(synthesis or [])

    def invoke_with_tools(self, **_kwargs):
        return next(self.responses)

    def invoke(self, *_args, **_kwargs):
        return type("Response", (), {
            "content": next(self.synthesis),
            "usage": {"total_tokens": 5},
        })()


def response(*, content=None, tool=None, arguments=None, tokens=10):
    calls = [] if tool is None else [ToolCall("call-1", tool, json.dumps(arguments or {}))]
    return LLMToolResponse(content=content, tool_calls=calls, model="mock", usage={"total_tokens": tokens})


def test_standard_orchestrator_runs_two_isolated_subagents(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_app.py").write_text("def test_main():\n    pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Run with sample.\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="sample"\nversion="0.1.0"\n[project.scripts]\nsample="app:main"\n',
        encoding="utf-8",
    )
    architecture = {
        "entry_points": [{
            "path": "src/app.py", "kind": "application", "description": "main entry",
            "evidence": [{"path": "src/app.py", "line_start": 1, "claim": "defines main"}],
        }],
        "module_map": [],
        "call_flows": [{
            "name": "main", "steps": ["main", "return"],
            "evidence": [{"path": "src/app.py", "line_start": 1, "line_end": 2, "claim": "main body"}],
        }],
        "risks": [],
    }
    runtime = {
        "run_commands": [{
            "command": "sample", "purpose": "run CLI",
            "evidence": [{"path": "pyproject.toml", "line_start": 4, "claim": "console script"}],
        }],
        "risks": [],
        "reading_path": ["README.md", "src/app.py"],
    }
    llm = ScriptedLLM([
        response(tool="search_code", arguments={"pattern": "def main", "glob": "*.py"}),
        response(tool="Finish", arguments={"answer": json.dumps(architecture)}),
        response(tool="parse_manifest", arguments={"path": "pyproject.toml"}),
        response(tool="Finish", arguments={"answer": json.dumps(runtime)}),
    ])
    config = RepoLensConfig(root=tmp_path, mode="standard", subagent_max_steps=3)
    report = RepositoryOrchestrator(config, llm=llm).analyze()

    assert report.metadata.mode == "standard"
    assert report.metadata.tokens == 40
    assert report.call_flows[0].name == "main"
    assert any(item.command == "sample" for item in report.run_commands)
    assert report.reading_path[:2] == ["README.md", "src/app.py"]
    assert EvidenceValidator(tmp_path).validate_report(report) == []


def test_invalid_subagent_evidence_is_dropped(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("sample\n", encoding="utf-8")
    architecture = {
        "entry_points": [{
            "path": "ghost.py", "kind": "application", "description": "invented",
            "evidence": [{"path": "ghost.py", "line_start": 1, "claim": "not real"}],
        }]
    }
    llm = ScriptedLLM([
        response(content=json.dumps(architecture)),
        response(content=json.dumps({"reading_path": ["ghost.py"]})),
    ])
    report = RepositoryOrchestrator(
        RepoLensConfig(root=tmp_path, mode="standard"), llm=llm
    ).analyze()
    assert report.entry_points == []
    assert "ghost.py" not in report.reading_path


def test_existing_evidence_does_not_justify_invented_command(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("run pytest\n", encoding="utf-8")
    architecture = {"findings": []}
    runtime = {"findings": [{
        "type": "run_command",
        "title": "deploy-production",
        "description": "invented",
        "evidence": {"path": "README.md", "claim": "unrelated", "line_start": 1},
    }]}
    llm = ScriptedLLM([response(content=json.dumps(architecture)), response(content=json.dumps(runtime))])
    report = RepositoryOrchestrator(
        RepoLensConfig(root=tmp_path, mode="standard"), llm=llm
    ).analyze()
    assert all(item.command != "deploy-production" for item in report.run_commands)


def test_step_exhaustion_forces_bounded_structured_synthesis(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def main():\n    pass\n", encoding="utf-8")
    architecture = json.dumps({"findings": [{
        "type": "entry_point",
        "title": "app.py",
        "description": "main",
        "evidence": {"path": "app.py", "claim": "defines main", "line_start": 1},
    }]})
    runtime = json.dumps({"findings": [{
        "type": "reading_path", "title": "app.py", "evidence": {"path": "app.py", "claim": "source"}
    }]})
    llm = ScriptedLLM(
        [
            response(tool="Read", arguments={"path": "app.py"}),
            response(tool="Read", arguments={"path": "app.py"}),
        ],
        synthesis=[architecture, runtime],
    )
    report = RepositoryOrchestrator(
        RepoLensConfig(root=tmp_path, mode="standard", subagent_max_steps=1), llm=llm
    ).analyze()
    assert report.entry_points[0].path == "app.py"
    assert report.reading_path == ["app.py"]
