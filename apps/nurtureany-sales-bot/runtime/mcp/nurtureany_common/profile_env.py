"""Profile dotenv helpers for NurtureAny MCP adapters."""

from __future__ import annotations

import os
from pathlib import Path


def profile_env_value(name: str) -> str:
    """Return an env value from process env or the active Hermes profile .env."""

    value = os.environ.get(name, "").strip()
    if value:
        return value

    for base_name in ("HERMES_HOME", "HERMES_PROFILE_DIR"):
        base = os.environ.get(base_name, "").strip()
        if not base:
            continue
        value = dotenv_value(Path(base) / ".env", name)
        if value:
            return value
    return ""


def dotenv_value(path: Path, name: str) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, raw_value = line.split("=", 1)
        if key.strip() != name:
            continue
        return _clean_dotenv_value(raw_value)
    return ""


def _clean_dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()
