#!/usr/bin/env python3
"""Reviewed learning-candidate MCP adapter for StaffAny Data Bot."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env


load_profile_env()

PROFILE_NAME = "staffanydatabot"
LESSON_CANDIDATES_DIR_ENV = "STAFFANY_DATA_LEARNING_CANDIDATES_DIR"
LESSON_RUNTIME_DIR_ENV = "STAFFANY_DATA_LEARNING_RUNTIME_DIR"
LESSON_CANDIDATE_STATUSES = {"pending_review", "needs_more_evidence", "approved_for_repo_promotion", "rejected", "promoted"}
LESSON_CANDIDATE_REVIEW_MARKER = "human reviewed lesson"
LESSON_CANDIDATE_RISK_CLASSES = {"low", "medium", "high"}
LESSON_CANDIDATE_TARGET_SURFACES = {
    "skill_reference",
    "soul",
    "mcp_contract",
    "config_template",
    "regression_case",
    "runbook",
    "research_wiki",
    "app_manifest",
}

mcp = FastMCP(
    "staffany_data_learning",
    instructions=(
        "Reviewed learning-candidate adapter for StaffAny Data Bot. It records "
        "safe behavior-level corrections as pending_review runtime candidates, "
        "lists/reads candidates for human review, records human review status "
        "updates, and never changes active bot behavior or stores raw Slack "
        "transcripts, raw query rows, secrets, or PII."
    ),
)


def _profile_runtime_dir() -> Path:
    raw_runtime = os.environ.get(LESSON_RUNTIME_DIR_ENV, "").strip()
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


def _lesson_candidates_dir() -> Path:
    raw = os.environ.get(LESSON_CANDIDATES_DIR_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    return _profile_runtime_dir() / "lesson-candidates"


def _safe_file_stem(value: str) -> str:
    source = str(value or "")
    safe_name = re.sub(r"[^A-Za-z0-9_.:-]+", "_", source).strip("._")
    if safe_name:
        return safe_name[:120]
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _lesson_candidate_path(lesson_id: str) -> Path:
    return _lesson_candidates_dir() / f"{_safe_file_stem(lesson_id)}.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _load_lesson_candidate(lesson_id: str) -> dict[str, Any]:
    path = _lesson_candidate_path(lesson_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _iter_lesson_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    directory = _lesson_candidates_dir()
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return candidates
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict):
            candidates.append(payload)
    return candidates


def _blocked(message: str, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": message,
        "source": "StaffAny Data Bot profile-runtime reviewed lesson candidates",
        "scope": scope,
        "confidence": "blocked",
        "caveat": (
            "No candidate was written or activated. Reviewed learning must use safe summaries only "
            "and requires repo promotion before behavior changes."
        ),
    }


def _clean_lesson_text(value: str, *, max_length: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_length]


def _looks_like_phone(value: str) -> bool:
    for match in re.finditer(r"(?<![A-Za-z0-9])\+?\d[\d\s().-]{6,}\d(?![A-Za-z0-9])", value):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            continue
        if len(digits) >= 8 and (candidate.startswith("+") or re.search(r"[\s().-]", candidate)):
            return True
    return False


def _lesson_payload_unsafe(*values: str) -> str:
    combined = "\n".join(str(value or "") for value in values)
    secret_patterns = (
        r"xox[baprs]-",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"(?i)(api[_ -]?key|private[_ -]?app[_ -]?token|oauth[_ -]?token|client[_ -]?secret)\s*[:=]",
        r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._-]+",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    )
    for pattern in secret_patterns:
        if re.search(pattern, combined):
            return "unsafe_payload:secret_or_token"

    if re.search(
        r"(?im)^\s*(user|assistant|bot|<@U[A-Z0-9]+|[A-Za-z .'-]{1,40}):\s+.+\n\s*"
        r"(user|assistant|bot|<@U[A-Z0-9]+|[A-Za-z .'-]{1,40}):",
        combined,
    ):
        return "unsafe_payload:raw_transcript_shape"
    if re.search(r"(?i)\b(user|assistant|bot|<@U[A-Z0-9]+)\s*:\s+.{1,500}\b(user|assistant|bot|<@U[A-Z0-9]+)\s*:", combined):
        return "unsafe_payload:raw_transcript_shape"

    if re.search(r'(?i)"rows"\s*:\s*\[|"properties"\s*:\s*\{|"query"\s*:\s*|raw_query_rows|raw query rows', combined):
        return "unsafe_payload:raw_query_or_source_rows"
    if re.search(r'(?i)"email"\s*:|"phone"\s*:|"mobilephone"\s*:|"nric"\s*:|"fin"\s*:', combined):
        return "unsafe_payload:pii_field"

    pii_text = "\n".join(str(value or "") for value in values[1:])
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", pii_text, flags=re.IGNORECASE):
        return "unsafe_payload:email_like_text"
    if _looks_like_phone(pii_text):
        return "unsafe_payload:phone_number_like_text"
    if re.search(r"(?i)\b(NRIC|FIN|passport|bank account|salary|employee payroll detail)\b", pii_text):
        return "unsafe_payload:sensitive_employee_or_financial_data"
    return ""


def _lesson_reviewer_is_automation(reviewer: str) -> bool:
    lowered = re.sub(r"\s+", " ", str(reviewer or "").strip().lower())
    if not lowered:
        return True
    explicit_markers = (
        "staffanydatabot",
        "staffany data bot",
        "da ta hermz",
        "data learning mcp",
        "hermes automation",
    )
    if any(marker in lowered for marker in explicit_markers):
        return True
    return any(re.search(rf"\b{re.escape(marker)}\b", lowered) for marker in ("automation", "bot", "agent", "system"))


def _lesson_status_transition_blocker(current_status: str, next_status: str) -> str:
    current = current_status or "pending_review"
    if current == "promoted" and next_status != "promoted":
        return "promoted candidates are immutable except idempotent promoted confirmation."
    if next_status == "promoted" and current != "approved_for_repo_promotion":
        return "promoted requires current status approved_for_repo_promotion."
    if current == "rejected" and next_status not in {"rejected", "needs_more_evidence"}:
        return "rejected candidates cannot be approved or promoted without first recording more evidence."
    return ""


def _compact_review_history(record: dict[str, Any]) -> list[dict[str, str]]:
    history = record.get("review_history")
    if not isinstance(history, list):
        return []
    compact_history: list[dict[str, str]] = []
    for event in history[-50:]:
        if not isinstance(event, dict):
            continue
        compact_history.append(
            {
                "at": str(event.get("at") or ""),
                "from_status": str(event.get("from_status") or ""),
                "to_status": str(event.get("to_status") or ""),
                "reviewer": str(event.get("reviewer") or ""),
                "review_notes": str(event.get("review_notes") or ""),
                "repo_commit_sha": str(event.get("repo_commit_sha") or ""),
                "live_verified_at": str(event.get("live_verified_at") or ""),
                "live_verification_summary": str(event.get("live_verification_summary") or ""),
            }
        )
    return compact_history


def _review_history_safety_text(record: dict[str, Any]) -> str:
    history = record.get("review_history")
    if not isinstance(history, list):
        return ""
    review_text = []
    for event in history[-50:]:
        if not isinstance(event, dict):
            continue
        review_text.append(str(event.get("review_notes") or ""))
        review_text.append(str(event.get("live_verification_summary") or ""))
    return "\n".join(review_text)


def _compact_lesson_candidate(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "lesson_id": str(record.get("lesson_id") or ""),
        "created_at": str(record.get("created_at") or ""),
        "source_thread_permalink": str(record.get("source_thread_permalink") or ""),
        "source_summary": str(record.get("source_summary") or ""),
        "proposed_rule": str(record.get("proposed_rule") or ""),
        "applies_to": str(record.get("applies_to") or ""),
        "target_repo_surface": str(record.get("target_repo_surface") or ""),
        "risk_class": str(record.get("risk_class") or ""),
        "status": str(record.get("status") or "pending_review"),
        "reviewer": str(record.get("reviewer") or ""),
        "review_notes": str(record.get("review_notes") or ""),
        "reviewed_at": str(record.get("reviewed_at") or ""),
        "review_history": _compact_review_history(record),
        "repo_commit_sha": str(record.get("repo_commit_sha") or ""),
        "live_verified_at": str(record.get("live_verified_at") or ""),
        "live_verification_summary": str(record.get("live_verification_summary") or ""),
        "promotion_policy": str(record.get("promotion_policy") or ""),
        "source_of_truth_boundary": str(record.get("source_of_truth_boundary") or ""),
        "honcho_used": bool(record.get("honcho_used", False)),
        "active_behavior_changed": bool(record.get("active_behavior_changed", False)),
        "will_mutate_staffany_data": bool(record.get("will_mutate_staffany_data", False)),
    }


@mcp.tool()
def record_staffany_data_lesson_candidate(
    source_summary: str,
    proposed_rule: str,
    applies_to: str,
    target_repo_surface: str,
    risk_class: str,
    source_thread_permalink: str = "",
    lesson_id: str = "",
) -> dict[str, Any]:
    """Record a safe pending reviewed-learning candidate in the profile runtime store."""

    source_thread_permalink = _clean_lesson_text(source_thread_permalink, max_length=300)
    source_summary = _clean_lesson_text(source_summary, max_length=800)
    proposed_rule = _clean_lesson_text(proposed_rule, max_length=800)
    applies_to = _clean_lesson_text(applies_to, max_length=300)
    target_repo_surface = _clean_lesson_text(target_repo_surface, max_length=80)
    risk_class = _clean_lesson_text(risk_class, max_length=20).lower()
    if not source_summary or not proposed_rule or not applies_to or not target_repo_surface or not risk_class:
        return _blocked(
            "source_summary, proposed_rule, applies_to, target_repo_surface, and risk_class are required.",
            {"lesson_candidates": "required-fields"},
        )
    if target_repo_surface not in LESSON_CANDIDATE_TARGET_SURFACES:
        return _blocked(
            "target_repo_surface must be one of skill_reference, soul, mcp_contract, config_template, regression_case, runbook, research_wiki, or app_manifest.",
            {"target_repo_surface": target_repo_surface},
        )
    if risk_class not in LESSON_CANDIDATE_RISK_CLASSES:
        return _blocked("risk_class must be low, medium, or high.", {"risk_class": risk_class})

    unsafe_reason = _lesson_payload_unsafe(source_thread_permalink, source_summary, proposed_rule, applies_to)
    if unsafe_reason:
        return _blocked(
            "Lesson candidates must not contain raw Slack transcripts, raw query rows, secrets, tokens, PII, phone numbers, bank details, NRIC/FIN, or employee-level payroll detail.",
            {"reason": unsafe_reason},
        )

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if lesson_id:
        safe_lesson_id = _safe_file_stem(str(lesson_id).strip())
    else:
        digest = hashlib.sha256(f"{source_summary}\n{proposed_rule}\n{applies_to}".encode("utf-8")).hexdigest()[:10]
        safe_lesson_id = f"lesson-{now.replace(':', '').replace('+', 'Z')}-{digest}"
    if not safe_lesson_id:
        return _blocked("lesson_id could not be normalized.", {"lesson_candidates": "invalid-id"})

    path = _lesson_candidate_path(safe_lesson_id)
    if path.exists():
        return _blocked("A lesson candidate already exists for this lesson_id.", {"lesson_id": safe_lesson_id})

    record = {
        "lesson_id": safe_lesson_id,
        "created_at": now,
        "source_thread_permalink": source_thread_permalink,
        "source_summary": source_summary,
        "proposed_rule": proposed_rule,
        "applies_to": applies_to,
        "target_repo_surface": target_repo_surface,
        "risk_class": risk_class,
        "status": "pending_review",
        "reviewer": "",
        "review_notes": "",
        "reviewed_at": "",
        "review_history": [],
        "repo_commit_sha": "",
        "live_verified_at": "",
        "live_verification_summary": "",
        "promotion_policy": "Runtime candidate only. Human review must promote approved behavior into the repo packet, tests, deployment, and live smoke before use.",
        "source_of_truth_boundary": "Does not override StaffAny registries, BigQuery, Customer 360, Slack identity rules, safety rules, or approved repo references.",
        "honcho_used": False,
        "active_behavior_changed": False,
        "will_mutate_staffany_data": False,
    }
    try:
        _atomic_write_json(path, record)
    except OSError as error:
        return _blocked(f"Lesson candidate write failed: {error.__class__.__name__}", {"lesson_id": safe_lesson_id})

    return {
        "answer": _compact_lesson_candidate(record),
        "source": "StaffAny Data Bot profile-runtime reviewed lesson candidates",
        "scope": {"lesson_id": safe_lesson_id, "lesson_candidates_dir": str(_lesson_candidates_dir()), "status": "pending_review"},
        "confidence": "verified",
        "caveat": "Candidate only. It does not change bot behavior until reviewed, promoted into the repo packet, verified, deployed, and live-checked.",
    }


@mcp.tool()
def list_staffany_data_lesson_candidates(status: str = "", limit: int = 20) -> dict[str, Any]:
    """List compact StaffAny Data Bot lesson candidates from the profile runtime store."""

    status = str(status or "").strip()
    if status and status not in LESSON_CANDIDATE_STATUSES:
        return _blocked(
            "status must be one of pending_review, needs_more_evidence, approved_for_repo_promotion, rejected, or promoted.",
            {"status": status},
        )
    try:
        safe_limit = min(max(0, int(limit)), 100)
    except (TypeError, ValueError):
        safe_limit = 20

    candidates = []
    for record in _iter_lesson_candidates():
        candidate_status = str(record.get("status") or "pending_review").strip()
        if status and candidate_status != status:
            continue
        compact = _compact_lesson_candidate(record)
        unsafe_reason = _lesson_payload_unsafe(
            compact.get("source_thread_permalink", ""),
            compact.get("source_summary", ""),
            compact.get("proposed_rule", ""),
            compact.get("applies_to", ""),
            compact.get("review_notes", ""),
            compact.get("live_verification_summary", ""),
            _review_history_safety_text(record),
        )
        if unsafe_reason:
            compact = {
                "lesson_id": compact.get("lesson_id") or "",
                "status": candidate_status,
                "created_at": compact.get("created_at") or "",
                "redacted": True,
                "redaction_reason": unsafe_reason,
            }
        candidates.append(compact)

    candidates.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    returned = candidates[:safe_limit]
    return {
        "answer": {
            "candidates": returned,
            "returned_count": len(returned),
            "total_matching_count": len(candidates),
            "status_filter": status or "all",
            "valid_statuses": sorted(LESSON_CANDIDATE_STATUSES),
        },
        "source": "StaffAny Data Bot profile-runtime reviewed lesson candidates",
        "scope": {"lesson_candidates_dir": str(_lesson_candidates_dir()), "limit": safe_limit},
        "confidence": "verified",
        "caveat": "Runtime candidates are not durable behavior until promoted into the repo packet, verified, deployed, and live-checked.",
    }


@mcp.tool()
def read_staffany_data_lesson_candidate(lesson_id: str) -> dict[str, Any]:
    """Read one StaffAny Data Bot lesson candidate by id."""

    lesson_id = _safe_file_stem(str(lesson_id or "").strip())
    if not lesson_id:
        return _blocked("lesson_id is required to read a lesson candidate.", {"lesson_candidates": "required-id"})
    record = _load_lesson_candidate(lesson_id)
    if not record:
        return _blocked("No lesson candidate found for this lesson_id.", {"lesson_id": lesson_id})
    compact = _compact_lesson_candidate(record)
    unsafe_reason = _lesson_payload_unsafe(
        compact.get("source_thread_permalink", ""),
        compact.get("source_summary", ""),
        compact.get("proposed_rule", ""),
        compact.get("applies_to", ""),
        compact.get("review_notes", ""),
        compact.get("live_verification_summary", ""),
        _review_history_safety_text(record),
    )
    if unsafe_reason:
        return _blocked(
            "Lesson candidate contains material that should not be returned through Slack/MCP.",
            {"lesson_id": lesson_id, "reason": unsafe_reason},
        )
    return {
        "answer": compact,
        "source": "StaffAny Data Bot profile-runtime reviewed lesson candidates",
        "scope": {"lesson_id": lesson_id, "lesson_candidates_dir": str(_lesson_candidates_dir())},
        "confidence": "verified",
        "caveat": "Read-only candidate. It does not change bot behavior until promoted into the repo packet, verified, deployed, and live-checked.",
    }


@mcp.tool()
def update_staffany_data_lesson_candidate_status(
    lesson_id: str,
    status: str,
    reviewer: str,
    review_notes: str,
    approval_marker: str,
    repo_commit_sha: str = "",
    live_verified_at: str = "",
    live_verification_summary: str = "",
) -> dict[str, Any]:
    """Update one StaffAny Data Bot lesson candidate's human review status."""

    lesson_id = _safe_file_stem(str(lesson_id or "").strip())
    status = _clean_lesson_text(status, max_length=80)
    reviewer = _clean_lesson_text(reviewer, max_length=200)
    review_notes = _clean_lesson_text(review_notes, max_length=1000)
    approval_marker = _clean_lesson_text(approval_marker, max_length=80).lower()
    repo_commit_sha = _clean_lesson_text(repo_commit_sha, max_length=80)
    live_verified_at = _clean_lesson_text(live_verified_at, max_length=120)
    live_verification_summary = _clean_lesson_text(live_verification_summary, max_length=1000)

    if not lesson_id:
        return _blocked("lesson_id is required to update a lesson candidate.", {"lesson_candidates": "required-id"})
    if status not in LESSON_CANDIDATE_STATUSES:
        return _blocked(
            "status must be one of pending_review, needs_more_evidence, approved_for_repo_promotion, rejected, or promoted.",
            {"status": status},
        )
    if not reviewer or not review_notes:
        return _blocked("reviewer and review_notes are required for lesson candidate status updates.", {"lesson_id": lesson_id})
    if approval_marker != LESSON_CANDIDATE_REVIEW_MARKER:
        return _blocked(
            f'approval_marker must be exactly "{LESSON_CANDIDATE_REVIEW_MARKER}".',
            {"lesson_id": lesson_id, "approval_marker_present": bool(approval_marker)},
        )
    if _lesson_reviewer_is_automation(reviewer):
        return _blocked("Bot, automation, agent, or system identities cannot approve, reject, or promote lesson candidates.", {"reviewer": reviewer})

    unsafe_reason = _lesson_payload_unsafe("", review_notes, live_verification_summary)
    if unsafe_reason:
        return _blocked(
            "Review notes and live verification summary must not contain raw Slack transcripts, raw query rows, secrets, tokens, PII, phone numbers, bank details, NRIC/FIN, or employee-level payroll detail.",
            {"reason": unsafe_reason},
        )

    record = _load_lesson_candidate(lesson_id)
    if not record:
        return _blocked("No lesson candidate found for this lesson_id.", {"lesson_id": lesson_id})

    current_status = str(record.get("status") or "pending_review").strip() or "pending_review"
    blocked_transition = _lesson_status_transition_blocker(current_status, status)
    if blocked_transition:
        return _blocked(blocked_transition, {"lesson_id": lesson_id, "current_status": current_status, "requested_status": status})

    if status == "promoted":
        if not repo_commit_sha or not re.fullmatch(r"[0-9a-fA-F]{7,64}", repo_commit_sha):
            return _blocked("promoted requires a repo_commit_sha of 7-64 hex characters.", {"lesson_id": lesson_id})
        if not live_verified_at or not live_verification_summary:
            return _blocked(
                "promoted requires live_verified_at and live_verification_summary after deploy/live checks.",
                {"lesson_id": lesson_id},
            )

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    history = record.get("review_history") if isinstance(record.get("review_history"), list) else []
    event = {
        "at": now,
        "from_status": current_status,
        "to_status": status,
        "reviewer": reviewer,
        "review_notes": review_notes,
    }
    if status == "promoted":
        event.update(
            {
                "repo_commit_sha": repo_commit_sha,
                "live_verified_at": live_verified_at,
                "live_verification_summary": live_verification_summary,
            }
        )
    history.append(event)

    record.update(
        {
            "status": status,
            "reviewer": reviewer,
            "review_notes": review_notes,
            "reviewed_at": now,
            "review_history": history[-50:],
            "honcho_used": False,
            "active_behavior_changed": False,
            "will_mutate_staffany_data": False,
        }
    )
    if status == "promoted":
        record["repo_commit_sha"] = repo_commit_sha
        record["live_verified_at"] = live_verified_at
        record["live_verification_summary"] = live_verification_summary

    try:
        _atomic_write_json(_lesson_candidate_path(lesson_id), record)
    except OSError as error:
        return _blocked(f"Lesson candidate status update failed: {error.__class__.__name__}", {"lesson_id": lesson_id})

    return {
        "answer": {
            **_compact_lesson_candidate(record),
            "previous_status": current_status,
            "approval_marker_used": approval_marker,
            "auto_behavior_change": False,
        },
        "source": "StaffAny Data Bot profile-runtime reviewed lesson candidates",
        "scope": {"lesson_id": lesson_id, "lesson_candidates_dir": str(_lesson_candidates_dir()), "status": status},
        "confidence": "verified",
        "caveat": "Runtime status only. Approved lessons still require repo promotion; promoted requires deploy and live verification evidence.",
    }


if __name__ == "__main__":
    mcp.run()
