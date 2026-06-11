from __future__ import annotations

import os
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def load_profile_env(profile_name: str = "revopsbot") -> None:
    explicit_paths = [
        os.environ.get("REVOPS_BOT_PROFILE_ENV", "").strip(),
        os.environ.get("HERMES_PROFILE_ENV", "").strip(),
    ]
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    candidates = [Path(path) for path in explicit_paths if path]
    if hermes_home:
        candidates.append(Path(hermes_home) / ".env")
    try:
        candidates.append(Path.home() / ".hermes" / "profiles" / profile_name / ".env")
    except RuntimeError:
        pass

    seen: set[Path] = set()
    for candidate in candidates:
        path = candidate.expanduser()
        if path in seen or not path.exists():
            continue
        seen.add(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(line)
            if not parsed:
                continue
            key, value = parsed
            if not os.environ.get(key):
                os.environ[key] = value
