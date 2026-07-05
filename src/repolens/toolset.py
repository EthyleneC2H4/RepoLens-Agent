"""Construction of the repository's read-only tool registry."""

from hello_agents import ToolRegistry

from repolens.config import RepoLensConfig
from repolens.tools import ParseManifestTool, ScanRepoTool
from repolens.tools.read import SafeReadTool


def build_readonly_registry(config: RepoLensConfig) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register_tool(
        ScanRepoTool(
            config.root,
            max_depth=config.max_depth,
            max_files=config.max_files,
            ignore_patterns=config.ignore_patterns,
        )
    )
    registry.register_tool(ParseManifestTool(config.root, max_file_bytes=config.max_file_bytes))
    registry.register_tool(SafeReadTool(config.root, max_file_bytes=config.max_file_bytes))
    return registry
