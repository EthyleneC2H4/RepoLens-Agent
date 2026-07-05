"""RepoLens command-line interface."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from repolens.analyzer import FastAnalyzer
from repolens.config import RepoLensConfig
from repolens.orchestrator import RepositoryOrchestrator
from repolens.renderers import write_report


app = typer.Typer(no_args_is_help=True, help="Analyze local repositories with file evidence.")


@app.callback()
def main() -> None:
    """RepoLens command group."""


@app.command()
def analyze(
    path: Annotated[Path, typer.Argument(help="Local repository path")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output directory")] = None,
    mode: Annotated[str, typer.Option(help="Analysis mode: fast or standard")] = "fast",
    output_format: Annotated[str, typer.Option("--format", help="md, json, or both")] = "both",
    max_depth: Annotated[int, typer.Option(help="Maximum scan depth")] = 4,
    max_files: Annotated[int, typer.Option(help="Maximum files to scan")] = 5_000,
) -> None:
    """Analyze PATH and write an evidence-backed report."""
    default_output = Path("reports") / datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        config = RepoLensConfig(
            root=path,
            output_dir=output or default_output,
            mode=mode,
            output_format=output_format,
            max_depth=max_depth,
            max_files=max_files,
        )
        report = (
            FastAnalyzer(config).analyze()
            if config.mode == "fast"
            else RepositoryOrchestrator(config).analyze()
        )
        written = write_report(report, config.output_dir or default_output, config.output_format)
    except (ValidationError, ValueError, RuntimeError, OSError) as exc:
        typer.echo(f"analysis failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(f"Analyzed {report.metadata.files_scanned} files in {report.metadata.mode} mode.")
    for result in written:
        typer.echo(str(result))
