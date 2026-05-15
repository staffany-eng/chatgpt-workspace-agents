#!/usr/bin/env python3
"""HubSpot-source inbound exception monitor for Hermes no-agent cron.

The monitor is intentionally quiet on healthy runs. It reads HubSpot
Conversations through the existing NurtureAny HubSpot MCP adapter, emits only
internal exception rows, and never mutates HubSpot or sends external messages.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


AUTOMATION_PREFIX = "NurtureAny automation:"
DEFAULT_CALLER_EMAIL = "eugene@staffany.com"
DEFAULT_LOOKBACK_MINUTES = 30
DEFAULT_LIMIT = 20
DEFAULT_ACK_SLA_MINUTES = 5
DEFAULT_FIRST_TOUCH_SLA_MINUTES = 15
DEFAULT_WARNING_MINUTES_BEFORE_SLA = 5
MAX_NOTIFIED_KEYS = 500
STATE_VERSION = 1
HERMES_VENV_REEXEC_ENV = "_NURTUREANY_INBOUND_MONITOR_HERMES_VENV"


class MonitorError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _profile_dir() -> Path:
    configured_profile = _env("HERMES_PROFILE_DIR")
    if configured_profile:
        return Path(configured_profile).expanduser()
    configured_home = _env("HERMES_HOME")
    if configured_home:
        home_path = Path(configured_home).expanduser()
        if (home_path / ".env").exists():
            return home_path
        profile_path = home_path / "profiles" / "nurtureanysalesbot"
        if profile_path.exists():
            return profile_path
    installed_profile = Path(__file__).resolve().parents[1]
    if (installed_profile / ".env").exists():
        return installed_profile
    return Path.home() / ".hermes" / "profiles" / "nurtureanysalesbot"


def ensure_runtime_python() -> None:
    """Use the Hermes venv when cron invokes the script through /usr/bin/env python3."""

    if os.environ.get(HERMES_VENV_REEXEC_ENV):
        return
    hermes_home = _profile_dir().parents[1]
    venv_python = hermes_home / "hermes-agent" / "venv" / "bin" / "python"
    if not venv_python.exists():
        return
    current = Path(sys.executable)
    target = venv_python
    if current == target:
        return
    os.environ[HERMES_VENV_REEXEC_ENV] = "1"
    os.execv(str(target), [str(target), *sys.argv])


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
        if not key:
            continue
        if key in os.environ and not key.startswith("NURTUREANY_INBOUND_MONITOR_"):
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def _runtime_root() -> Path:
    current = Path(__file__).resolve()
    repo_runtime = current.parents[1]
    if (repo_runtime / "mcp").exists():
        return repo_runtime
    profile_runtime = _profile_dir() / "runtime"
    if (profile_runtime / "mcp").exists():
        return profile_runtime
    return repo_runtime


def _load_hubspot_module():
    mcp_dir = _runtime_root() / "mcp"
    if str(mcp_dir) not in sys.path:
        sys.path.insert(0, str(mcp_dir))
    import hubspot_nurtureany_server

    return hubspot_nurtureany_server


def _default_state_path() -> Path:
    configured = _env("NURTUREANY_INBOUND_MONITOR_STATE_PATH")
    if configured:
        return Path(configured).expanduser()
    return _profile_dir() / "state" / "nurtureany_inbound_monitor.json"


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_as_of(value: str) -> datetime:
    parsed = _parse_dt(value)
    return parsed or datetime.now(timezone.utc)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": STATE_VERSION, "notified_keys": []}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": STATE_VERSION, "notified_keys": []}
    if not isinstance(state, dict):
        return {"version": STATE_VERSION, "notified_keys": []}
    notified = state.get("notified_keys")
    if not isinstance(notified, list):
        state["notified_keys"] = []
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _latest_message_after(args: argparse.Namespace, state: dict[str, Any], as_of: datetime) -> str:
    if args.latest_message_after:
        return args.latest_message_after
    lookback_minutes = max(1, int(args.lookback_minutes))
    lookback_floor = as_of - timedelta(minutes=lookback_minutes)
    cursor = _parse_dt(state.get("last_seen_latest_message_after"))
    if cursor:
        # Keep a lookback floor even when a cursor exists so a newly received
        # thread can become stale on a later cron tick and still be audited.
        padded_cursor = cursor - timedelta(minutes=args.first_touch_sla_minutes + DEFAULT_WARNING_MINUTES_BEFORE_SLA)
        lookback_floor = min(lookback_floor, padded_cursor)
    return _safe_iso(lookback_floor)


def _load_fixture(path: str) -> dict[str, Any]:
    if not path:
        raise MonitorError("--fixture path is required when fixture mode is used.")
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("audit_result"), dict):
        return payload["audit_result"]
    if isinstance(payload, dict):
        return payload
    raise MonitorError("Fixture must be a JSON object or contain audit_result.")


def _call_audit(args: argparse.Namespace, latest_message_after: str) -> dict[str, Any]:
    if args.fixture:
        return _load_fixture(args.fixture)
    module = _load_hubspot_module()
    return module.audit_inbound_sla(
        slack_user_email=args.caller_email,
        thread_status="OPEN",
        inbox_id=args.inbox_id,
        latest_message_after=latest_message_after,
        limit=args.max_results,
        ack_sla_minutes=args.ack_sla_minutes,
        first_touch_sla_minutes=args.first_touch_sla_minutes,
        resolve_slack_alerts=False,
        exclude_existing_customers=False,
    )


def _assert_read_only_result(result: dict[str, Any]) -> None:
    answer = result.get("answer") if isinstance(result.get("answer"), dict) else {}
    if answer.get("will_mutate_hubspot") or answer.get("external_message_sending"):
        raise MonitorError("Inbound monitor requires read-only audit output with no HubSpot mutation or external send.")


def _first_company(row: dict[str, Any]) -> dict[str, Any]:
    companies = ((row.get("hubspot_context") or {}).get("companies") or [])
    if companies and isinstance(companies[0], dict):
        return companies[0]
    return {}


def _account_status(row: dict[str, Any]) -> str:
    return str(_first_company(row).get("account_status") or "").strip().lower()


def _lead_context_missing(row: dict[str, Any]) -> bool:
    context = row.get("lead_context") if isinstance(row.get("lead_context"), dict) else {}
    if context.get("context_status") == "missing":
        return True
    return not any(
        str(context.get(key) or "").strip()
        for key in ("company_name", "contact_role", "email_domain", "summary")
    )


def _missing_clean_lead(row: dict[str, Any]) -> bool:
    gaps = {str(item).lower() for item in (row.get("hubspot_gaps") or [])}
    important = {
        "missing contact",
        "missing company",
        "missing current tools",
        "missing buying role",
        "missing lead source",
    }
    return bool(gaps & important) or _lead_context_missing(row)


def _duplicate_groups(result: dict[str, Any]) -> set[str]:
    answer = result.get("answer") if isinstance(result.get("answer"), dict) else {}
    groups = set()
    for item in answer.get("duplicate_summary") or []:
        if not isinstance(item, dict):
            continue
        group = str(item.get("duplicate_group") or "")
        if group and group != "needs-check" and int(item.get("alert_count") or 0) > 1:
            groups.add(group)
    return groups


def _age_minutes(row: dict[str, Any], as_of: datetime) -> int | None:
    alert_time = _parse_dt(row.get("alert_time"))
    if not alert_time:
        return None
    return int((as_of - alert_time).total_seconds() // 60)


def _eta(row: dict[str, Any], first_touch_sla_minutes: int) -> str:
    if row.get("first_customer_touch_time"):
        return "done"
    alert_time = _parse_dt(row.get("alert_time"))
    if not alert_time:
        return "now"
    return _safe_iso(alert_time + timedelta(minutes=first_touch_sla_minutes))


def _action_status(row: dict[str, Any], duplicate_group_keys: set[str], as_of: datetime, warning_threshold: int) -> str:
    if _account_status(row) == "customer":
        return "customer"
    duplicate_group = str(row.get("duplicate_group") or "")
    if duplicate_group in duplicate_group_keys:
        return "duplicate"
    if row.get("first_touch_sla_status") == "miss" or row.get("sla_status") == "miss":
        return "stale"
    if not row.get("assigned_owner"):
        return "new"
    if row.get("first_touch_source") == "missing":
        age = _age_minutes(row, as_of)
        if age is not None and age >= warning_threshold:
            return "new"
    if _missing_clean_lead(row):
        return "touched" if row.get("first_touch_sla_status") == "pass" else "new"
    return ""


def _next_step(status: str, row: dict[str, Any]) -> str:
    if status == "customer":
        return "route to support/CSM check; do not treat as new sales inbound"
    if status == "duplicate":
        return "review duplicate group in HubSpot before chasing separately"
    if status == "stale":
        return "manager chase or manually reassign now"
    if not row.get("assigned_owner"):
        return "assign owner and reply before SLA"
    if _missing_clean_lead(row):
        return "complete clean-lead context in HubSpot before AE handoff"
    if status == "new":
        return "owner to reply before first-touch SLA"
    return "review HubSpot Conversations"


def _row_key(row: dict[str, Any], status: str, step: str) -> str:
    identity = row.get("hubspot_thread_id") or row.get("alert_id") or row.get("alert_time") or "unknown"
    return "|".join([str(identity), status, step])


def action_rows_from_result(
    result: dict[str, Any],
    as_of: datetime,
    first_touch_sla_minutes: int = DEFAULT_FIRST_TOUCH_SLA_MINUTES,
) -> list[dict[str, str]]:
    if result.get("confidence") == "blocked":
        return [
            {
                "key": "blocked",
                "line": "Owner: unknown | Status: blocked | Next step: check HubSpot auth/config for inbound monitor | ETA: now",
            }
        ]
    answer = result.get("answer") if isinstance(result.get("answer"), dict) else {}
    duplicate_groups = _duplicate_groups(result)
    warning_threshold = max(0, first_touch_sla_minutes - DEFAULT_WARNING_MINUTES_BEFORE_SLA)
    actions: list[dict[str, str]] = []
    for row in answer.get("audit_rows") or []:
        if not isinstance(row, dict):
            continue
        status = _action_status(row, duplicate_groups, as_of, warning_threshold)
        if not status:
            continue
        step = _next_step(status, row)
        owner = str(row.get("assigned_owner") or "unknown").strip() or "unknown"
        eta = "now" if status in {"customer", "duplicate", "stale"} else _eta(row, first_touch_sla_minutes)
        actions.append(
            {
                "key": _row_key(row, status, step),
                "line": f"Owner: {owner} | Status: {status} | Next step: {step} | ETA: {eta}",
            }
        )
    return actions


def _update_state(state: dict[str, Any], result: dict[str, Any], as_of: datetime, emitted_keys: list[str]) -> dict[str, Any]:
    answer = result.get("answer") if isinstance(result.get("answer"), dict) else {}
    last_seen = state.get("last_seen_latest_message_after") or ""
    for row in answer.get("audit_rows") or []:
        if not isinstance(row, dict):
            continue
        for value in (row.get("first_hubspot_outbound_at"), row.get("alert_time"), row.get("first_customer_touch_time")):
            parsed = _parse_dt(value)
            if parsed and (not _parse_dt(last_seen) or parsed > _parse_dt(last_seen)):
                last_seen = _safe_iso(parsed)
    notified = list(dict.fromkeys([*(state.get("notified_keys") or []), *emitted_keys]))[-MAX_NOTIFIED_KEYS:]
    return {
        "version": STATE_VERSION,
        "last_scan_at": _safe_iso(as_of),
        "last_seen_latest_message_after": last_seen,
        "notified_keys": notified,
    }


def format_report(
    result: dict[str, Any],
    actions: list[dict[str, str]],
    state: dict[str, Any],
    dry_run: bool,
) -> str:
    if result.get("confidence") == "blocked":
        caveat = result.get("caveat") or result.get("answer") or "HubSpot inbound monitor blocked."
        return "\n".join(
            [
                f"{AUTOMATION_PREFIX} HubSpot inbound monitor blocked",
                "Source: HubSpot Conversations",
                "Confidence: blocked",
                f"Caveat: {caveat}",
            ]
        )
    notified = set(state.get("notified_keys") or [])
    fresh_actions = [action for action in actions if action["key"] not in notified]
    if not fresh_actions:
        return ""
    dry_label = " DRY RUN" if dry_run else ""
    lines = [
        f"{AUTOMATION_PREFIX} HubSpot inbound monitor{dry_label}",
        f"Rows: {len(fresh_actions)}",
        *[action["line"] for action in fresh_actions],
        "Source: HubSpot Conversations and CRM activity",
        "Scope: open inbound threads; HubSpot-source SLA triage",
        f"Confidence: {result.get('confidence') or 'needs-check'}",
        f"Caveat: {result.get('caveat') or 'Internal exception report only; no HubSpot mutation or external send.'}",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a quiet HubSpot-source inbound exception report.")
    parser.add_argument("--once", action="store_true", help="Run one monitor pass. Present for cron readability.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing runtime state.")
    parser.add_argument("--fixture", default="", help="Fixture JSON containing an audit_result object or raw audit result.")
    parser.add_argument("--state-path", default=str(_default_state_path()))
    parser.add_argument("--as-of", default="")
    parser.add_argument("--caller-email", default=_env("NURTUREANY_INBOUND_MONITOR_CALLER_EMAIL", DEFAULT_CALLER_EMAIL))
    parser.add_argument("--inbox-id", default=_env("NURTUREANY_INBOUND_MONITOR_INBOX_ID", ""))
    parser.add_argument(
        "--lookback-minutes",
        type=int,
        default=int(_env("NURTUREANY_INBOUND_MONITOR_LOOKBACK_MINUTES", str(DEFAULT_LOOKBACK_MINUTES)) or DEFAULT_LOOKBACK_MINUTES),
    )
    parser.add_argument("--latest-message-after", default="")
    parser.add_argument("--max-results", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--ack-sla-minutes", type=int, default=DEFAULT_ACK_SLA_MINUTES)
    parser.add_argument("--first-touch-sla-minutes", type=int, default=DEFAULT_FIRST_TOUCH_SLA_MINUTES)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ensure_runtime_python()
    load_profile_env()
    args = parse_args(argv or sys.argv[1:])
    if not args.dry_run and not _truthy(_env("NURTUREANY_INBOUND_MONITOR_ENABLED", "false")):
        return 0
    state_path = Path(args.state_path).expanduser()
    state = load_state(state_path)
    as_of = _parse_as_of(args.as_of)
    try:
        latest_after = _latest_message_after(args, state, as_of)
        result = _call_audit(args, latest_after)
        _assert_read_only_result(result)
        actions = action_rows_from_result(result, as_of, args.first_touch_sla_minutes)
        report = format_report(result, actions, state, args.dry_run)
        if report:
            print(report)
        if not args.dry_run:
            emitted_keys = [action["key"] for action in actions]
            save_state(state_path, _update_state(state, result, as_of, emitted_keys))
        return 0 if result.get("confidence") != "blocked" else 1
    except Exception as error:
        print(
            "\n".join(
                [
                    f"{AUTOMATION_PREFIX} HubSpot inbound monitor blocked",
                    "Source: HubSpot Conversations",
                    "Confidence: blocked",
                    f"Caveat: {error}",
                ]
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
