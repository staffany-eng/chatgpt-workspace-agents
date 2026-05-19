#!/usr/bin/env python3
"""Deterministic reviewed-lesson digest for Hermes no-agent cron.

This script surfaces safe pending lesson candidates. It does not approve,
reject, promote, call HubSpot, call Honcho, call GitHub, or use an LLM.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


AUTOMATION_PREFIX = "NurtureAny automation:"
DEFAULT_PROFILE = "nurtureanysalesbot"
DEFAULT_STATUS = "pending_review"
DEFAULT_MAX_ITEMS = 20
HERMES_VENV_REEXEC_ENV = "_NURTUREANY_LESSON_REVIEW_DIGEST_HERMES_VENV"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _profile_dir() -> Path:
    configured_profile = _env("HERMES_PROFILE_DIR")
    if configured_profile:
        return Path(configured_profile).expanduser()
    configured_home = _env("HERMES_HOME")
    if configured_home:
        home_path = Path(configured_home).expanduser()
        if (home_path / ".env").exists():
            return home_path
        profile_path = home_path / "profiles" / DEFAULT_PROFILE
        if profile_path.exists():
            return profile_path
    installed_profile = Path(__file__).resolve().parents[1]
    if (installed_profile / ".env").exists():
        return installed_profile
    return Path.home() / ".hermes" / "profiles" / DEFAULT_PROFILE


def ensure_runtime_python() -> None:
    """Use the Hermes venv when cron invokes the script through /usr/bin/env python3."""

    if os.environ.get(HERMES_VENV_REEXEC_ENV):
        return
    hermes_home = _profile_dir().parents[1]
    venv_python = hermes_home / "hermes-agent" / "venv" / "bin" / "python"
    if not venv_python.exists():
        return
    if Path(sys.executable) == venv_python:
        return
    os.environ[HERMES_VENV_REEXEC_ENV] = "1"
    os.execv(str(venv_python), [str(venv_python), *sys.argv])


def load_profile_env() -> None:
    """Load profile .env values when Hermes does not inject them into no-agent jobs."""

    env_path = _profile_dir() / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def lesson_candidates_dir() -> Path:
    configured = _env("NURTUREANY_LESSON_CANDIDATES_DIR")
    if configured:
        return Path(configured).expanduser()
    return _profile_dir() / "lesson-candidates"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a safe NurtureAny reviewed-lesson digest.")
    parser.add_argument("--candidates-dir", default="", help="Override lesson-candidates directory.")
    parser.add_argument("--status", default=DEFAULT_STATUS, help="Candidate status to surface. Default: pending_review.")
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS)
    parser.add_argument("--dry-run", action="store_true", help="Label output as dry-run. This script never mutates state.")
    return parser.parse_args(argv)


def load_candidates(directory: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return candidates
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payload["_source_file"] = path.name
            candidates.append(payload)
    return candidates


def _compact_text(value: Any, max_length: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_length]


def unsafe_reason(record: dict[str, Any]) -> str:
    values = [
        record.get("source_summary", ""),
        record.get("proposed_rule", ""),
        record.get("applies_to", ""),
        record.get("target_repo_surface", ""),
        record.get("review_notes", ""),
    ]
    combined = "\n".join(str(value or "") for value in values)
    lowered = combined.lower()
    secret_patterns = (
        r"xox[baprs]-",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"(?i)(api[_ -]?key|private[_ -]?app[_ -]?token|oauth[_ -]?token|client[_ -]?secret|authorization:\s*bearer)\s*[:=]?",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    )
    for pattern in secret_patterns:
        if re.search(pattern, combined):
            return "secret_or_token"
    if re.search(r"(?im)^\s*(user|assistant|bot|<@U[A-Z0-9]+|[A-Za-z .'-]{1,40}):\s+.+\n\s*(user|assistant|bot|<@U[A-Z0-9]+|[A-Za-z .'-]{1,40}):", combined):
        return "raw_slack_transcript"
    if re.search(r'(?i)"properties"\s*:\s*\{|"hs_communication_body"\s*:|"mobilephone"\s*:|"phone"\s*:', combined):
        return "raw_hubspot_row_or_pii_field"
    phone_like = r"(?:\+?\d[\s().-]*){8,}"
    if re.search(rf"(?i)(phone|mobile|whatsapp|sms|contact number|number)\D{{0,40}}{phone_like}", combined):
        return "phone_number"
    if re.search(r"(?i)\b(contact export|attendee export|bulk export)\b", combined):
        return "contact_export"
    if re.search(r"(?i)\b(email|firstname|lastname|phone|mobilephone)\s*,\s*(email|firstname|lastname|phone|mobilephone)\b", combined):
        return "contact_export"
    if "raw slack transcript" in lowered or "raw hubspot row" in lowered:
        return "raw_private_material"
    return ""


def filtered_candidates(candidates: list[dict[str, Any]], status: str, max_items: int) -> list[dict[str, Any]]:
    selected = [candidate for candidate in candidates if str(candidate.get("status") or "pending_review").strip() == status]
    selected.sort(key=lambda item: str(item.get("created_at") or ""))
    return selected[: max(1, min(max_items, 100))]


def recommended_action(record: dict[str, Any], redacted: bool) -> str:
    if redacted:
        return "Do not approve from Slack digest; inspect runtime JSON safely and reject or rewrite as a safe candidate."
    status = str(record.get("status") or "pending_review")
    if status == "needs_more_evidence":
        return "Add evidence or reject."
    return "Reject, mark needs_more_evidence, or approve_for_repo_promotion."


def format_digest(candidates: list[dict[str, Any]], *, status: str, dry_run: bool = False) -> str:
    if not candidates:
        return ""
    dry_label = " DRY RUN" if dry_run else ""
    lines = [
        f"{AUTOMATION_PREFIX} Learning review{dry_label}",
        f"Queue: {status}",
        f"Pending safe summaries: {len(candidates)}",
        "Source: profile-runtime lesson-candidates JSON",
        "Scope: review-only; no behavior change, HubSpot mutation, Honcho memory, Curator, Kanban dispatch, or GitHub push",
        "",
    ]
    for index, record in enumerate(candidates, start=1):
        lesson_id = _compact_text(record.get("lesson_id") or record.get("_source_file") or "unknown", 160)
        reason = unsafe_reason(record)
        redacted = bool(reason)
        lines.append(f"{index}. Lesson: {lesson_id}")
        lines.append(f"   Created: {_compact_text(record.get('created_at') or 'unknown', 80)}")
        lines.append(f"   Status: {_compact_text(record.get('status') or 'pending_review', 80)}")
        if redacted:
            lines.append(f"   Redacted: unsafe candidate content ({reason})")
        else:
            permalink = _compact_text(record.get("source_thread_permalink") or "none", 300)
            lines.append(f"   Source: {permalink}")
            lines.append(f"   Proposed rule: {_compact_text(record.get('proposed_rule'), 500)}")
            lines.append(f"   Applies to: {_compact_text(record.get('applies_to'), 220)}")
            lines.append(f"   Target repo surface: {_compact_text(record.get('target_repo_surface'), 120)}")
            lines.append(f"   Risk: {_compact_text(record.get('risk_class'), 80)}")
        lines.append(f"   Recommended reviewer action: {recommended_action(record, redacted)}")
        lines.append("")
    lines.append("Promotion rule: approved lessons still need repo change, verify, deploy, and live check before `promoted`.")
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    ensure_runtime_python()
    load_profile_env()
    args = parse_args(argv or sys.argv[1:])
    directory = Path(args.candidates_dir).expanduser() if args.candidates_dir else lesson_candidates_dir()
    candidates = filtered_candidates(load_candidates(directory), args.status, args.max_items)
    digest = format_digest(candidates, status=args.status, dry_run=args.dry_run)
    if digest:
        print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
