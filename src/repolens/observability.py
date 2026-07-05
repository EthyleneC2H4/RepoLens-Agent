"""Minimal sanitized event payloads for public analysis traces."""

import re
from typing import Any


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, str):
        value = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-***", value)
        value = re.sub(r"Bearer\s+\S+", "Bearer ***", value, flags=re.IGNORECASE)
        value = re.sub(
            r"(?i)(api[_-]?key|token|password|secret)(\s*[:=]\s*)[^\s,;]+",
            r"\1\2***",
            value,
        )
        return value
    if isinstance(value, dict):
        return {key: redact_sensitive(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value
