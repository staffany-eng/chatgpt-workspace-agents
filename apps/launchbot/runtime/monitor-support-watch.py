#!/usr/bin/env python3
"""No-agent Launchbot weekly monitor for support-watch reports."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROFILE_DIR = Path(os.path.expanduser(os.environ.get("HERMES_PROFILE_DIR") or os.environ.get("HERMES_HOME") or "~/.hermes/profiles/launchbot"))
MCP_DIR_CANDIDATES = [
    SCRIPT_DIR / "mcp",
    SCRIPT_DIR.parent / "runtime" / "mcp",
    PROFILE_DIR / "source" / "launchbot" / "runtime" / "mcp",
]
for mcp_dir in MCP_DIR_CANDIDATES:
    if (mcp_dir / "launchbot_support_watch_core.py").exists() and str(mcp_dir) not in sys.path:
        sys.path.insert(0, str(mcp_dir))
        break

import launchbot_support_watch_core as support_core  # noqa: E402


DEFAULT_STATE_PATH = "~/.hermes/profiles/launchbot/runtime/support-watch-state.json"
DEFAULT_OUTPUT_CHANNEL_NAME = "all-bugs-production"
DEFAULT_CRON_SCHEDULE = "0 1 * * 4"
DEDUPE_CHANNEL_IDS_ENV = "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS"
EDT_JQL_ENV = "LAUNCHBOT_SUPPORT_WATCH_EDT_JQL"
AUTOMATION_PREFIX = "Launchbot automation:"


def state_path_from_env() -> Path:
    return Path(os.path.expanduser(os.environ.get("LAUNCHBOT_SUPPORT_WATCH_STATE_PATH", DEFAULT_STATE_PATH)))


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "reports": [], "posted_report_signatures": {}, "finding_signatures": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "reports": [], "posted_report_signatures": {}, "finding_signatures": {}}
    if not isinstance(state, dict):
        return {"version": 1, "reports": [], "posted_report_signatures": {}, "finding_signatures": {}}
    state.setdefault("version", 1)
    state.setdefault("reports", [])
    state.setdefault("posted_report_signatures", {})
    state.setdefault("finding_signatures", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def slack_post(method: str, body: dict[str, Any]) -> dict[str, Any]:
    data = urllib.parse.urlencode({key: value for key, value in body.items() if value not in (None, "")}).encode("utf-8")
    request = urllib.request.Request(
        urllib.parse.urljoin(support_core.SLACK_API_BASE_URL, method),
        data=data,
        headers={
            "Authorization": f"Bearer {support_core.token('SLACK_BOT_TOKEN')}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": support_core.USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise support_core.LaunchbotSupportWatchError(support_core.safe_error(f"Slack API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise support_core.LaunchbotSupportWatchError(support_core.safe_error(f"Slack API request failed: {reason}")) from error
    if not payload.get("ok"):
        raise support_core.LaunchbotSupportWatchError(support_core.safe_error(f"Slack API returned error: {payload.get('error') or 'unknown_error'}"))
    return payload


def output_channel_name() -> str:
    return os.environ.get("LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME", DEFAULT_OUTPUT_CHANNEL_NAME).strip().lstrip("#") or DEFAULT_OUTPUT_CHANNEL_NAME


def output_channel_id() -> tuple[str, str]:
    configured = os.environ.get("LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID", "").strip()
    if configured:
        return configured, "env"
    channel_name = output_channel_name()
    resolved = support_core.resolve_slack_channel_id(channel_name)
    if not resolved:
        raise support_core.LaunchbotSupportWatchError(f"Could not resolve Slack channel #{channel_name}.")
    return resolved, "resolved"


def ensure_output_channel_membership(channel_id: str) -> str:
    info = support_core.slack_api("conversations.info", {"channel": channel_id})
    channel = info.get("channel") or {}
    if channel.get("is_member") is True:
        return "member"
    slack_post("conversations.join", {"channel": channel_id})
    return "joined"


def safe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_items = []
    for finding in findings:
        safe_items.append(
            {
                "signature": str(finding.get("signature") or ""),
                "summary": support_core.safe_text(finding.get("summary") or "", 180),
                "product_area": support_core.safe_text(finding.get("product_area") or "", 80),
                "severity": support_core.safe_text(finding.get("severity") or "", 40),
                "signal": support_core.safe_text(finding.get("signal") or "", 80),
                "ticket_count": int(finding.get("ticket_count") or 0),
                "ticket_ids": [str(ticket_id) for ticket_id in finding.get("ticket_ids", [])[: support_core.MAX_SAFE_TICKETS_PER_FINDING]],
                "evidence_tickets": [
                    {
                        "id": str(ticket.get("id") or ""),
                        "ticket_id": str(ticket.get("ticket_id") or ""),
                        "source_type": str(ticket.get("source_type") or ""),
                        "source_ref": str(ticket.get("source_ref") or ""),
                        "summary": support_core.safe_text(ticket.get("summary") or "", 220),
                        "state": support_core.safe_text(ticket.get("state") or "", 80),
                        "team_assignee_id": str(ticket.get("team_assignee_id") or ""),
                        "admin_assignee_id": str(ticket.get("admin_assignee_id") or ""),
                        "created_at": str(ticket.get("created_at") or ""),
                        "updated_at": str(ticket.get("updated_at") or ""),
                        "source_url": str(ticket.get("source_url") or ""),
                        "hubspot_company_id": str(ticket.get("hubspot_company_id") or ""),
                        "company_name": support_core.safe_text(ticket.get("company_name") or "", 120),
                        "organisation_id": str(ticket.get("organisation_id") or ""),
                        "organisation_name": support_core.safe_text(ticket.get("organisation_name") or "", 120),
                    }
                    for ticket in (finding.get("evidence_tickets") or [])[: support_core.MAX_SAFE_TICKETS_PER_FINDING]
                    if isinstance(ticket, dict)
                ],
                "status": support_core.safe_text(finding.get("status") or "", 40),
            }
        )
    return safe_items


def apply_prior_state_dedupe(report: dict[str, Any], state: dict[str, Any]) -> None:
    seen = set((state.get("finding_signatures") or {}).keys())
    new_findings = []
    for finding in report.get("new_findings", []) or []:
        signature = str(finding.get("signature") or "")
        if signature and signature in seen:
            finding["status"] = support_core.STATE_STATUS_DEDUPED
            finding["dedupe_match"] = {"source": "support_watch_state"}
            report.setdefault("deduped_findings", []).append(finding)
        else:
            new_findings.append(finding)
    report["new_findings"] = new_findings
    report["report_signature"] = support_core.report_signature(new_findings)
    report["slack_report"] = support_core.build_slack_report(report)


def record_state(
    state: dict[str, Any],
    report: dict[str, Any],
    *,
    channel_id: str = "",
    post_ts: str = "",
    action: str,
) -> None:
    now = support_core.isoformat(support_core.now_utc())
    state["last_window_end"] = report.get("window", {}).get("end", now)
    report_signature = str(report.get("report_signature") or "")
    if report_signature:
        state.setdefault("posted_report_signatures", {})[report_signature] = {
            "posted_at": now if post_ts else "",
            "channel_id": channel_id,
            "post_ts": post_ts,
            "action": action,
        }
    for finding in safe_findings((report.get("new_findings") or []) + (report.get("deduped_findings") or [])):
        signature = finding.get("signature")
        if signature:
            state.setdefault("finding_signatures", {})[signature] = {
                **finding,
                "updated_at": now,
            }
    state.setdefault("reports", []).append(
        {
            "window": report.get("window") or {},
            "action": action,
            "report_signature": report_signature,
            "new_finding_count": len(report.get("new_findings") or []),
            "deduped_finding_count": len(report.get("deduped_findings") or []),
            "ticket_count": int(report.get("ticket_count") or 0),
            "support_item_count": int(report.get("support_item_count") or report.get("ticket_count") or 0),
            "source_status": report.get("source_status") or {},
            "channel_id": channel_id,
            "post_ts": post_ts,
            "updated_at": now,
        }
    )
    state["reports"] = state["reports"][-20:]


def window_start_from_state(args: argparse.Namespace, state: dict[str, Any]):
    end = support_core.parse_iso(args.window_end, support_core.now_utc())
    if args.window_start:
        return support_core.parse_iso(args.window_start, end - timedelta(days=args.lookback_days)), end
    last_end = str(state.get("last_window_end") or "")
    if last_end:
        return support_core.parse_iso(last_end, end - timedelta(days=args.lookback_days)), end
    return end - timedelta(days=max(1, int(args.lookback_days or support_core.DEFAULT_LOOKBACK_DAYS))), end


def run_monitor(args: argparse.Namespace) -> dict[str, Any]:
    state_path = Path(os.path.expanduser(args.state_path)) if args.state_path else state_path_from_env()
    state = load_state(state_path)
    lookback_days = int(os.environ.get("LAUNCHBOT_SUPPORT_WATCH_LOOKBACK_DAYS", args.lookback_days))
    max_tickets = int(os.environ.get("LAUNCHBOT_SUPPORT_WATCH_MAX_TICKETS", args.max_tickets))
    args.lookback_days = lookback_days
    start, end = window_start_from_state(args, state)

    preview = support_core.preview_weekly_support_watch_report(
        window_start_iso=support_core.isoformat(start),
        window_end_iso=support_core.isoformat(end),
        lookback_days=lookback_days,
        max_tickets=max_tickets,
        include_traces=not args.skip_traces,
    )
    if preview.get("confidence") == "blocked":
        return {
            "dry_run": args.dry_run,
            "action": "blocked",
            "state_path": str(state_path),
            "reason": preview.get("answer"),
            "transcript_persisted": False,
            "will_post_message": False,
        }

    report = preview.get("answer") or {}
    apply_prior_state_dedupe(report, state)
    report_signature = str(report.get("report_signature") or "")
    if report_signature and report_signature in state.get("posted_report_signatures", {}):
        action = "skipped"
        reason = "duplicate-report-signature"
    elif not report.get("new_findings"):
        action = "skipped"
        reason = "no-new-findings"
    else:
        action = "would_post" if args.dry_run else "posted"
        reason = ""

    channel_id = ""
    channel_id_source = ""
    channel_membership = ""
    post_ts = ""
    if action == "posted":
        channel_id, channel_id_source = output_channel_id()
        channel_membership = ensure_output_channel_membership(channel_id)
        text = str(report.get("slack_report") or "")
        if not text.startswith(AUTOMATION_PREFIX):
            raise support_core.LaunchbotSupportWatchError("Support-watch Slack report must start with Launchbot automation:.")
        posted = slack_post(
            "chat.postMessage",
            {
                "channel": channel_id,
                "text": text,
                "unfurl_links": "false",
                "unfurl_media": "false",
            },
        )
        post_ts = str(posted.get("ts") or "")
    elif action == "would_post":
        try:
            channel_id, channel_id_source = output_channel_id()
        except support_core.LaunchbotSupportWatchError as error:
            channel_id = ""
            channel_id_source = f"blocked:{support_core.safe_error(str(error))}"

    if not args.dry_run:
        record_state(state, report, channel_id=channel_id, post_ts=post_ts, action=action)
        save_state(state_path, state)

    return {
        "dry_run": args.dry_run,
        "action": action,
        "reason": reason,
        "window": report.get("window") or {},
        "ticket_count": int(report.get("ticket_count") or 0),
        "support_item_count": int(report.get("support_item_count") or report.get("ticket_count") or 0),
        "source_status": report.get("source_status") or {},
        "new_finding_count": len(report.get("new_findings") or []),
        "deduped_finding_count": len(report.get("deduped_findings") or []),
        "report_signature": report_signature,
        "output_channel_name": output_channel_name(),
        "output_channel_id": channel_id,
        "output_channel_id_source": channel_id_source,
        "output_channel_membership": channel_membership,
        "state_path": str(state_path),
        "dedupe_channel_ids_env": DEDUPE_CHANNEL_IDS_ENV,
        "dedupe_channel_names_env": "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES",
        "edt_jql_env": EDT_JQL_ENV,
        "cron_schedule_utc": DEFAULT_CRON_SCHEDULE,
        "transcript_persisted": False,
        "will_post_message": action in {"posted", "would_post"},
        "will_create_ticket": False,
        "will_tag_engineer": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the weekly Launchbot support-watch monitor.")
    parser.add_argument("--dry-run", action="store_true", help="Preview findings without Slack posts or state writes.")
    parser.add_argument("--window-start", default="", help="ISO UTC start timestamp. Defaults to previous state window end or lookback.")
    parser.add_argument("--window-end", default="", help="ISO UTC end timestamp. Defaults to now.")
    parser.add_argument("--lookback-days", type=int, default=support_core.DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--max-tickets", type=int, default=support_core.DEFAULT_MAX_TICKETS)
    parser.add_argument("--state-path", default="")
    parser.add_argument("--skip-traces", action="store_true", help="Skip Pantheon trace heuristics.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_monitor(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
