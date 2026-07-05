import json

from repolens.agent_findings import parse_role_findings


def test_flat_architecture_protocol_maps_to_strict_schema() -> None:
    text = json.dumps({
        "findings": [{
            "type": "call_flow",
            "title": "CLI",
            "description": "entry flow",
            "evidence": {"path": "app.py", "claim": "main", "line_start": 1},
            "value": "console script -> main",
        }]
    })
    findings = parse_role_findings(text, "architecture")
    assert findings.call_flows[0].steps == ["console script", "main"]
    assert findings.call_flows[0].evidence[0].path == "app.py"


def test_flat_runtime_protocol_maps_commands_and_reading_path() -> None:
    text = json.dumps({
        "findings": [
            {"type": "run_command", "title": "pytest", "description": "tests", "evidence": {"path": "README.md", "claim": "documents command"}},
            {"type": "reading_path", "title": "README.md"},
        ]
    })
    findings = parse_role_findings(text, "runtime")
    assert findings.run_commands[0].command == "pytest"
    assert findings.reading_path == ["README.md"]
