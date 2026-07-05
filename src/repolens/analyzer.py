"""Deterministic repository analyzer used by the fast CLI mode."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import PurePosixPath
from time import perf_counter
from typing import Any

from hello_agents.tools.response import ToolStatus

from repolens.config import RepoLensConfig
from repolens.schemas import (
    AnalysisMetadata,
    AnalysisReport,
    EntryPoint,
    EvidenceRef,
    ModuleInfo,
    RiskItem,
    RunCommand,
    TechStackItem,
)
from repolens.tools.manifest import ParseManifestTool, SUPPORTED_MANIFESTS
from repolens.tools.scanner import ScanRepoTool


Clock = Callable[[], datetime]


class FastAnalyzer:
    """Build an evidence-backed report using only deterministic tools."""

    def __init__(self, config: RepoLensConfig, *, clock: Clock | None = None) -> None:
        if config.mode != "fast":
            raise ValueError("FastAnalyzer only supports mode='fast'")
        self.config = config
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def analyze(self) -> AnalysisReport:
        started = perf_counter()
        scan_response = ScanRepoTool(
            self.config.root,
            max_depth=self.config.max_depth,
            max_files=self.config.max_files,
            ignore_patterns=self.config.ignore_patterns,
        ).run({})
        if scan_response.status is not ToolStatus.SUCCESS:
            raise RuntimeError(scan_response.text)
        scan = scan_response.data
        files = sorted(
            entry["path"] for entry in scan["entries"] if entry["type"] == "file"
        )
        directories = sorted(
            entry["path"] for entry in scan["entries"] if entry["type"] == "directory"
        )

        manifest_tool = ParseManifestTool(
            self.config.root, max_file_bytes=self.config.max_file_bytes
        )
        manifests: list[dict[str, Any]] = []
        manifest_errors: list[str] = []
        for path in files:
            if PurePosixPath(path).name not in SUPPORTED_MANIFESTS:
                continue
            response = manifest_tool.run({"path": path})
            if response.status is ToolStatus.SUCCESS:
                manifests.append(response.data)
            else:
                manifest_errors.append(f"{path}: {response.text}")

        evidence = self._manifest_evidence(manifests)
        tech_stack = self._tech_stack(manifests, scan["extensions"])
        entry_points = self._entry_points(files)
        modules = self._module_map(directories)
        commands = self._run_commands(manifests, files)
        risks = self._risks(scan, files, manifests, manifest_errors)
        reading_path = self._reading_path(files, manifests, entry_points, modules)
        project_name = next(
            (item.get("name") for item in manifests if item.get("name")),
            scan["root_name"],
        )
        stack_names = ", ".join(item.name for item in tech_stack) or "unknown stack"

        return AnalysisReport(
            project_summary=(
                f"{project_name} contains {scan['files']} files across "
                f"{scan['directories']} scanned directories. Detected: {stack_names}."
            ),
            tech_stack=tech_stack,
            entry_points=entry_points,
            module_map=modules,
            run_commands=commands,
            risks=risks,
            reading_path=reading_path,
            evidence=evidence,
            metadata=AnalysisMetadata(
                mode="fast",
                source_root=str(self.config.root),
                generated_at=self.clock(),
                duration_ms=max(0, int((perf_counter() - started) * 1000)),
                files_scanned=scan["files"],
                directories_scanned=scan["directories"],
                manifests_parsed=len(manifests),
                tool_calls=1 + len(manifests) + len(manifest_errors),
            ),
        )

    @staticmethod
    def _ref(path: str, claim: str) -> EvidenceRef:
        return EvidenceRef(path=path, claim=claim)

    def _manifest_evidence(self, manifests: list[dict[str, Any]]) -> list[EvidenceRef]:
        return [self._ref(item["path"], f"Parsed {item['manifest_type']} manifest") for item in manifests]

    def _tech_stack(
        self, manifests: list[dict[str, Any]], extensions: dict[str, int]
    ) -> list[TechStackItem]:
        labels = {"python": "Python", "node": "Node.js", "go": "Go"}
        result: list[TechStackItem] = []
        for item in manifests:
            kind = item["manifest_type"]
            version = item.get("requires_python") or item.get("go_version")
            if kind == "node" and isinstance(item.get("engines"), dict):
                version = item["engines"].get("node")
            result.append(
                TechStackItem(
                    category="runtime",
                    name=labels[kind],
                    version=version,
                    evidence=[self._ref(item["path"], f"Declares {labels[kind]} project metadata")],
                )
            )
        if not result:
            extension_labels = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".go": "Go"}
            for suffix, label in extension_labels.items():
                if extensions.get(suffix):
                    result.append(TechStackItem(category="language", name=label))
        unique: dict[tuple[str, str], TechStackItem] = {}
        for item in result:
            unique.setdefault((item.category, item.name), item)
        return list(unique.values())

    def _entry_points(self, files: list[str]) -> list[EntryPoint]:
        names = {
            "main.py": "application",
            "app.py": "application",
            "cli.py": "command line",
            "__main__.py": "Python module",
            "main.go": "application",
            "index.js": "application",
            "index.ts": "application",
        }
        result: list[EntryPoint] = []
        for path in files:
            kind = names.get(PurePosixPath(path).name)
            if kind:
                result.append(
                    EntryPoint(
                        path=path,
                        kind=kind,
                        description=f"Candidate {kind} entry point inferred from its filename.",
                        evidence=[self._ref(path, "Conventional entry-point filename")],
                    )
                )
        return result[:20]

    def _module_map(self, directories: list[str]) -> list[ModuleInfo]:
        purposes = {
            "src": "application source code",
            "tests": "automated tests",
            "test": "automated tests",
            "docs": "documentation",
            "examples": "usage examples",
            "scripts": "development or automation scripts",
            "skills": "agent skill definitions",
        }
        result: list[ModuleInfo] = []
        for path in directories:
            if "/" in path:
                continue
            purpose = purposes.get(path.lower(), "top-level project module")
            result.append(ModuleInfo(path=path, purpose=purpose))
        return result

    def _run_commands(
        self, manifests: list[dict[str, Any]], files: list[str]
    ) -> list[RunCommand]:
        commands: list[RunCommand] = []
        for item in manifests:
            ref = [self._ref(item["path"], "Command inferred from manifest")]
            if item["manifest_type"] == "python":
                commands.append(RunCommand(command="pip install -e .", purpose="Install the project in editable mode", evidence=ref))
                for name in sorted(item.get("scripts", {})):
                    commands.append(RunCommand(command=name, purpose=f"Run the {name} console script", evidence=ref))
            elif item["manifest_type"] == "node":
                for name in sorted(item.get("scripts", {})):
                    commands.append(RunCommand(command=f"npm run {name}", purpose=f"Run the {name} package script", evidence=ref))
            elif item["manifest_type"] == "go":
                commands.append(RunCommand(command="go test ./...", purpose="Run all Go tests", evidence=ref))
        if any(path.startswith("tests/") or path.startswith("test/") for path in files) and any(
            item["manifest_type"] == "python" for item in manifests
        ):
            commands.append(RunCommand(command="python -m pytest", purpose="Run the Python test suite"))
        return commands

    def _risks(
        self,
        scan: dict[str, Any],
        files: list[str],
        manifests: list[dict[str, Any]],
        manifest_errors: list[str],
    ) -> list[RiskItem]:
        risks: list[RiskItem] = []
        if scan["truncated"]:
            risks.append(RiskItem(level="high", description="The scan reached its file limit; the report is incomplete."))
        if not manifests:
            risks.append(RiskItem(level="medium", description="No supported project manifest was parsed."))
        if manifest_errors:
            risks.append(RiskItem(level="medium", description="Some supported manifests could not be parsed: " + "; ".join(manifest_errors)))
        if not any(path.startswith("tests/") or path.startswith("test/") for path in files):
            risks.append(RiskItem(level="medium", description="No conventional test directory was found in the scanned depth."))
        if not any(PurePosixPath(path).name.lower().startswith("readme") for path in files):
            risks.append(RiskItem(level="low", description="No README file was found in the scanned depth."))
        return risks

    @staticmethod
    def _reading_path(
        files: list[str],
        manifests: list[dict[str, Any]],
        entry_points: list[EntryPoint],
        modules: list[ModuleInfo],
    ) -> list[str]:
        candidates = [
            *sorted(path for path in files if PurePosixPath(path).name.lower().startswith("readme")),
            *(item["path"] for item in manifests),
            *(item.path for item in entry_points),
            *(item.path for item in modules),
        ]
        return list(dict.fromkeys(candidates))[:20]
