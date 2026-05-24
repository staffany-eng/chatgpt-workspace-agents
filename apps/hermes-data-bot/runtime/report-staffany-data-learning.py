#!/usr/bin/env python3
"""No-agent reviewed-learning candidate report for StaffAny Data Bot."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROFILE_NAME = "staffanydatabot"
CANDIDATES_DIR_ENV = "STAFFANY_DATA_LEARNING_CANDIDATES_DIR"
RUNTIME_DIR_ENV = "STAFFANY_DATA_LEARNING_RUNTIME_DIR"
STATUSES = ("pending_review", "needs_more_evidence", "approved_for_repo_promotion", "rejected", "promoted")
RISK_CLASSES = ("low", "medium", "high")


def profile_runtime_dir() -> Path:
    raw_runtime = os.environ.get(RUNTIME_DIR_ENV, "").strip()
    if raw_runtime:
        return Path(raw_runtime).expanduser()
    for env_name in ("HERMES_PROFILE_DIR", "HERMES_HOME"):
        raw_profile = os.environ.get(env_name, "").strip()
        if not raw_profile:
            continue
        profile_path = Path(raw_profile).expanduser()
        if profile_path.name == "runtime":
            return profile_path
        if (profile_path / "config.yaml").exists() or profile_path.name == PROFILE_NAME:
            return profile_path / "runtime"
    return Path.home() / ".hermes" / "profiles" / PROFILE_NAME / "runtime"


def candidates_dir() -> Path:
    raw = os.environ.get(CANDIDATES_DIR_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    return profile_runtime_dir() / "lesson-candidates"


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_candidates(directory: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    unreadable = 0
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return records, 1
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            unreadable += 1
            continue
        if isinstance(payload, dict):
            records.append(payload)
        else:
            unreadable += 1
    return records, unreadable


def build_report(records: list[dict[str, Any]], unreadable: int, stale_days: int) -> list[str]:
    now = datetime.now(timezone.utc)
    status_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    pending_times: list[datetime] = []
    stale_pending = 0

    for record in records:
        status = str(record.get("status") or "pending_review")
        if status not in STATUSES:
            status = "invalid"
        status_counts[status] += 1

        risk = str(record.get("risk_class") or "unknown")
        if risk not in RISK_CLASSES:
            risk = "unknown"
        risk_counts[risk] += 1

        if status == "pending_review":
            created = parse_time(record.get("created_at"))
            if created is not None:
                pending_times.append(created)
                if (now - created).days >= stale_days:
                    stale_pending += 1

    oldest_pending = min(pending_times).isoformat() if pending_times else ""
    oldest_pending_age_days = max((now - min(pending_times)).days, 0) if pending_times else 0
    lines = [
        "staffany_data_learning_review_report:ok",
        (
            "lesson_candidates:"
            f"total={len(records)}:"
            f"pending={status_counts.get('pending_review', 0)}:"
            f"oldest_pending_age_days={oldest_pending_age_days}:"
            f"stale_pending={stale_pending}:"
            f"stale_threshold_days={stale_days}:"
            f"unreadable={unreadable}"
        ),
        "lesson_candidates_status:" + ":".join(f"{status}={status_counts.get(status, 0)}" for status in (*STATUSES, "invalid")),
        "lesson_candidates_risk:" + ":".join(f"{risk}={risk_counts.get(risk, 0)}" for risk in (*RISK_CLASSES, "unknown")),
        f"lesson_candidates_oldest_pending_created_at:{oldest_pending or 'none'}",
        "lesson_candidates_content:omitted",
    ]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Print safe counts/staleness for StaffAny Data Bot reviewed-learning candidates.")
    parser.add_argument("--stale-days", type=int, default=14)
    args = parser.parse_args()
    stale_days = max(1, min(int(args.stale_days), 3650))
    records, unreadable = load_candidates(candidates_dir())
    for line in build_report(records, unreadable, stale_days):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
