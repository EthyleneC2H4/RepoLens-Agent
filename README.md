# RepoLens Agent

RepoLens Agent analyzes a local code repository and produces deterministic,
evidence-backed Markdown and JSON reports. Week 1 provides a fully offline
`fast` mode; LLM-driven analysis is intentionally deferred to Week 2.

## Current capabilities

- Safe repository traversal with configurable depth and ignore rules.
- Python (`pyproject.toml`), Node (`package.json`), and Go (`go.mod`) manifest parsing.
- Structured Pydantic report schema with file evidence.
- CLI output in Markdown, JSON, or both formats.
- Local Ollama configuration for `qwen3.5:4b` (not required by fast mode).

## Quick start

Requirements: Python 3.12, `uv`, and optionally Ollama.

```bash
uv venv --python 3.12
source .venv/bin/activate
uv sync
```

Analyze a repository without calling an LLM:

```bash
repolens analyze ../HelloAgents --mode fast --format both
```

By default, reports are written to `reports/<timestamp>/`. Use `--output` for
a stable destination:

```bash
repolens analyze ../HelloAgents --output reports/helloagents --format both
```

## Local model configuration

The future agent workflow uses local Ollama with `qwen3.5:4b`:

```bash
ollama pull qwen3.5:4b
cp .env.example .env
```

```dotenv
LLM_MODEL_ID=qwen3.5:4b
LLM_API_KEY=ollama
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_TIMEOUT=120
```

Ollama ignores the API key; the non-empty value satisfies the vendored
HelloAgents configuration check.

## Tests

```bash
uv run pytest tests/repolens -q
uv run pytest tests/test_tool_response_protocol.py -q
```

## Project structure

```text
src/repolens/       RepoLens application code
hello_agents/       Vendored HelloAgents V1.0.0 framework baseline
tests/repolens/     RepoLens unit and CLI tests
docs/               Upstream framework reference documentation
examples/           Upstream framework examples
```

## Attribution and license

RepoLens Agent vendors code from
[HelloAgents V1.0.0](https://github.com/jjyaoao/HelloAgents/releases/tag/V1.0.0).
The upstream framework, its documentation, and derivative work remain subject
to CC BY-NC-SA 4.0. RepoLens-specific code consists of the repository analysis
workflow, tools, schemas, renderers, CLI, and evaluation assets.

This project is intended for learning and non-commercial portfolio use.
