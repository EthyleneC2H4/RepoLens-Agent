"""Construction of the repository's read-only tool registry."""

from typing import Any

from hello_agents import ToolRegistry
from hello_agents.tools.base import Tool

from repolens.config import RepoLensConfig
from repolens.tools import ParseManifestTool, ScanRepoTool
from repolens.tools.read import SafeReadTool
from repolens.tools.search import SearchCodeTool


class CountingTool(Tool):
    def __init__(self, wrapped: Tool, registry: "ReadOnlyRegistry") -> None:
        super().__init__(wrapped.name, wrapped.description)
        self.wrapped = wrapped
        self.registry = registry

    def get_parameters(self):
        return self.wrapped.get_parameters()

    def run(self, parameters: dict[str, Any]):
        self.registry.tool_calls += 1
        response = self.wrapped.run(parameters)
        self.registry.observations.append(
            {"tool": self.name, "output": response.text[:6_000]}
        )
        self.registry.observations = self.registry.observations[-6:]
        return response


class ReadOnlyRegistry(ToolRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.tool_calls = 0
        self.observations: list[dict[str, str]] = []

    def register_counted(self, tool: Tool) -> None:
        self.register_tool(CountingTool(tool, self))


def build_readonly_registry(config: RepoLensConfig) -> ReadOnlyRegistry:
    registry = ReadOnlyRegistry()
    registry.register_counted(
        ScanRepoTool(
            config.root,
            max_depth=config.max_depth,
            max_files=config.max_files,
            ignore_patterns=config.ignore_patterns,
        )
    )
    registry.register_counted(ParseManifestTool(config.root, max_file_bytes=config.max_file_bytes))
    registry.register_counted(
        SafeReadTool(
            config.root,
            max_file_bytes=config.max_file_bytes,
            max_output_lines=config.tool_output_max_lines,
            max_output_bytes=config.tool_output_max_bytes,
        )
    )
    registry.register_counted(SearchCodeTool(config.root))
    return registry
