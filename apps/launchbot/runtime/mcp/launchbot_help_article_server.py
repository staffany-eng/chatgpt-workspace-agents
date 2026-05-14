#!/usr/bin/env python3
"""Draft-only Intercom help article video slot updater for Launchbot."""

from __future__ import annotations

import html
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env


load_profile_env()

APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = APP_ROOT / "skills" / "help-article-generator" / "references" / "video-placement-registry.json"
INTERCOM_TIMEOUT_SECONDS = 30
INTERCOM_API_VERSION = "2.15"
DEFAULT_INTERCOM_APP_ID = "y12ertqm"
USER_AGENT = "StaffAny-Launchbot/1.0 (+https://staffany.com)"
LOOM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{2,}$")
LOOM_IFRAME_RE = re.compile(
    r"<iframe\b(?P<attrs>[^>]*?)\bsrc=(?P<quote>['\"])(?P<src>https?://(?:www\.)?loom\.com/(?:embed|share)/[A-Za-z0-9][A-Za-z0-9-]*(?:\?[^'\"]*)?)(?P=quote)(?P<tail>[^>]*)>\s*</iframe>",
    re.IGNORECASE | re.DOTALL,
)
HEADING_RE = re.compile(r"<h[1-6]\b", re.IGNORECASE)

mcp = FastMCP(
    "launchbot_help_article",
    instructions=(
        "Launchbot draft-only help article video update adapter. It accepts Loom share/embed URLs, "
        "resolves a registered help article video slot, previews one exact iframe-src patch, and can "
        "PUT the same checked body to Intercom with state=draft only. It never publishes, deletes, "
        "tags, moves collections, or rewrites article copy."
    ),
)


class LaunchbotHelpArticleError(RuntimeError):
    pass


def _registry_path() -> Path:
    raw = os.environ.get("LAUNCHBOT_VIDEO_PLACEMENT_REGISTRY", "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_REGISTRY_PATH


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LaunchbotHelpArticleError(f"Video placement registry missing: {path}") from error
    except json.JSONDecodeError as error:
        raise LaunchbotHelpArticleError(f"Video placement registry is invalid JSON: {path}") from error
    if registry.get("version") != 1 or not isinstance(registry.get("articles"), list):
        raise LaunchbotHelpArticleError("Video placement registry must have version=1 and articles[].")
    return registry


def _scope(article_hint: str, slot_id: str, will_mutate_intercom: bool) -> dict[str, Any]:
    return {
        "article_hint": (article_hint or "").strip(),
        "slot_id": (slot_id or "").strip(),
        "registry_path": str(_registry_path()),
        "supported_provider": "loom",
        "configured_slots_only": True,
        "will_mutate_intercom": will_mutate_intercom,
        "will_publish": False,
        "will_delete": False,
        "will_mutate_tags_or_collections": False,
    }


def _blocked(message: str, source: str, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "error": message,
        "source": source,
        "scope": scope,
        "confidence": "blocked",
        "will_publish": False,
        "caveat": "No Intercom update was performed. Video-only updates require a registered slot and a supported Loom embed URL.",
    }


def _safe_error(message: str) -> str:
    safe = str(message)
    for name in ("LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN", "INTERCOM_ACCESS_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            safe = safe.replace(value, f"[REDACTED_{name}]")
    return safe[:350]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _article_matches(article: dict[str, Any], hint: str) -> bool:
    normalized_hint = _normalize_text(hint)
    if not normalized_hint:
        return True
    fields = [
        article.get("article_key", ""),
        article.get("locale", ""),
        article.get("title", ""),
        article.get("public_url", ""),
        article.get("intercom_article_id", ""),
    ]
    return any(normalized_hint in _normalize_text(field) for field in fields)


def _resolve_slot(registry: dict[str, Any], article_hint: str, slot_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    articles = [article for article in registry.get("articles", []) if isinstance(article, dict)]
    article_candidates = [article for article in articles if _article_matches(article, article_hint)]
    normalized_slot = _normalize_text(slot_id)
    if normalized_slot:
        article_candidates = [
            article
            for article in article_candidates
            if any(_normalize_text(slot.get("slot_id", "")) == normalized_slot for slot in article.get("slots", []) if isinstance(slot, dict))
        ]
    if not article_candidates:
        raise LaunchbotHelpArticleError("No registered article slot matched the article hint and slot_id.")
    if len(article_candidates) > 1:
        keys = ", ".join(str(article.get("article_key") or article.get("title")) for article in article_candidates[:5])
        raise LaunchbotHelpArticleError(f"Article hint is ambiguous across registered slots: {keys}.")

    article = article_candidates[0]
    slots = [slot for slot in article.get("slots", []) if isinstance(slot, dict)]
    if normalized_slot:
        slots = [slot for slot in slots if _normalize_text(slot.get("slot_id", "")) == normalized_slot]
    if not slots:
        raise LaunchbotHelpArticleError("No registered video slot matched slot_id for the article.")
    if len(slots) > 1:
        raise LaunchbotHelpArticleError("Registered article has multiple video slots; pass slot_id.")
    slot = slots[0]
    if slot.get("provider") != "loom":
        raise LaunchbotHelpArticleError("Only registered Loom slots are supported in V1.")
    if slot.get("replace_policy") != "replace_next_video_after_anchor":
        raise LaunchbotHelpArticleError("Unsupported video replace_policy in registry.")
    if not slot.get("anchor_text"):
        raise LaunchbotHelpArticleError("Registered video slot is missing anchor_text.")
    if not article.get("intercom_article_id"):
        raise LaunchbotHelpArticleError("Registered article is missing intercom_article_id.")
    return article, slot


def normalize_loom_embed_url(raw_url: str) -> str:
    """Return an Intercom-safe Loom embed URL, or raise for unsupported inputs."""

    value = str(raw_url or "").strip()
    if not value:
        raise LaunchbotHelpArticleError("Loom URL is required.")
    if re.search(r"\.(mp4|mov|webm|m4v)(?:$|[?#])", value, flags=re.IGNORECASE):
        raise LaunchbotHelpArticleError("Raw video files are not supported. Use a Loom share or embed URL.")
    parsed = urllib.parse.urlparse(value)
    host = parsed.netloc.lower()
    if host not in {"loom.com", "www.loom.com"}:
        raise LaunchbotHelpArticleError("Only Loom share/embed URLs are supported in V1.")
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2 or path_parts[0] not in {"share", "embed"}:
        raise LaunchbotHelpArticleError("Loom URL must use /share/{id} or /embed/{id}.")
    video_id = path_parts[1].strip()
    if not LOOM_ID_RE.fullmatch(video_id):
        raise LaunchbotHelpArticleError("Loom URL is missing a valid video id.")
    return f"https://www.loom.com/embed/{video_id}"


def _anchor_variants(anchor_text: str) -> list[str]:
    anchor = str(anchor_text or "").strip()
    variants = [
        anchor,
        html.escape(anchor, quote=False),
        html.escape(anchor, quote=True),
        html.escape(anchor, quote=True).replace("&#x27;", "&#39;"),
    ]
    deduped: list[str] = []
    for variant in variants:
        if variant and variant not in deduped:
            deduped.append(variant)
    return deduped


def _find_anchor_span(body: str, anchor_text: str) -> tuple[int, int]:
    spans: list[tuple[int, int]] = []
    for variant in _anchor_variants(anchor_text):
        pattern = re.compile(re.escape(variant).replace(r"\ ", r"\s+"), re.IGNORECASE)
        for match in pattern.finditer(body):
            if match.span() not in spans:
                spans.append(match.span())
    if not spans:
        raise LaunchbotHelpArticleError("Registered anchor_text was not found in the current Intercom body.")
    if len(spans) > 1:
        raise LaunchbotHelpArticleError("Registered anchor_text matched multiple places in the current Intercom body.")
    return spans[0]


def _replace_iframe_src(iframe_html: str, new_src: str) -> str:
    return re.sub(r"\bsrc=(['\"])[^'\"]+\1", f'src="{new_src}"', iframe_html, count=1, flags=re.IGNORECASE)


def _build_video_patch(body: str, article: dict[str, Any], slot: dict[str, Any], new_video_src: str) -> dict[str, Any]:
    if not isinstance(body, str) or not body.strip():
        raise LaunchbotHelpArticleError("Current Intercom article body is empty.")

    _, anchor_end = _find_anchor_span(body, slot["anchor_text"])
    next_heading = HEADING_RE.search(body, anchor_end)
    region_end = next_heading.start() if next_heading else len(body)
    region = body[anchor_end:region_end]
    iframe_matches = list(LOOM_IFRAME_RE.finditer(region))
    if not iframe_matches:
        raise LaunchbotHelpArticleError("No Loom iframe was found after the registered anchor before the next heading.")
    if len(iframe_matches) > 1:
        raise LaunchbotHelpArticleError("Multiple Loom iframes were found after the registered anchor before the next heading.")

    match = iframe_matches[0]
    absolute_start = anchor_end + match.start()
    absolute_end = anchor_end + match.end()
    before_html = body[absolute_start:absolute_end]
    current_video = match.group("src")
    try:
        current_video_normalized = normalize_loom_embed_url(current_video)
    except LaunchbotHelpArticleError:
        current_video_normalized = current_video
    after_html = _replace_iframe_src(before_html, new_video_src)
    if before_html == after_html:
        raise LaunchbotHelpArticleError("New Loom embed URL is already present in the registered video slot.")

    updated_body = f"{body[:absolute_start]}{after_html}{body[absolute_end:]}"
    return {
        "article": {
            "article_key": article.get("article_key"),
            "title": article.get("title"),
            "locale": article.get("locale"),
            "public_url": article.get("public_url"),
            "intercom_article_id": article.get("intercom_article_id"),
        },
        "slot": {
            "slot_id": slot.get("slot_id"),
            "purpose": slot.get("purpose"),
            "anchor_text": slot.get("anchor_text"),
            "provider": slot.get("provider"),
            "replace_policy": slot.get("replace_policy"),
        },
        "current_video": current_video_normalized,
        "new_video": new_video_src,
        "patch_summary": {
            "operation": "replace_iframe_src_in_registered_video_slot",
            "anchor_text": slot.get("anchor_text"),
            "before_html": before_html,
            "after_html": after_html,
            "body_changed": updated_body != body,
        },
        "updated_body": updated_body,
    }


def _intercom_base_url() -> str:
    return (os.environ.get("LAUNCHBOT_INTERCOM_API_BASE_URL", "https://api.intercom.io").strip() or "https://api.intercom.io").rstrip("/")


def _intercom_token() -> str:
    value = os.environ.get("LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN", "").strip()
    if not value:
        raise LaunchbotHelpArticleError("Missing LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN.")
    return value


def _intercom_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{_intercom_base_url()}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {_intercom_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Intercom-Version": INTERCOM_API_VERSION,
            "User-Agent": USER_AGENT,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=INTERCOM_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LaunchbotHelpArticleError(_safe_error(f"Intercom API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotHelpArticleError(_safe_error(f"Intercom API request failed: {reason}")) from error


def _article_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("article")
    return nested if isinstance(nested, dict) else payload


def _read_intercom_article(article_id: str) -> dict[str, Any]:
    return _article_payload(_intercom_request("GET", f"/articles/{urllib.parse.quote(str(article_id))}"))


def _update_intercom_article_draft(article_id: str, updated_body: str) -> dict[str, Any]:
    return _article_payload(
        _intercom_request(
            "PUT",
            f"/articles/{urllib.parse.quote(str(article_id))}",
            {"body": updated_body, "state": "draft"},
        )
    )


def _draft_url(article_id: str, payload: dict[str, Any]) -> str:
    for key in ("url", "html_url", "admin_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    app_id = os.environ.get("LAUNCH_STEP3_INTERCOM_APP_ID", DEFAULT_INTERCOM_APP_ID).strip() or DEFAULT_INTERCOM_APP_ID
    return f"https://app.intercom.com/a/apps/{app_id}/articles/articles/{article_id}/show"


def _preview_patch(article_hint: str, loom_url: str, slot_id: str, will_mutate_intercom: bool) -> dict[str, Any]:
    scope = _scope(article_hint, slot_id, will_mutate_intercom)
    new_video = normalize_loom_embed_url(loom_url)
    registry = _load_registry()
    article, slot = _resolve_slot(registry, article_hint, slot_id)
    article_id = str(article["intercom_article_id"])
    payload = _read_intercom_article(article_id)
    body = payload.get("body") or ""
    patch = _build_video_patch(body, article, slot, new_video)
    return {
        **{key: value for key, value in patch.items() if key != "updated_body"},
        "will_publish": False,
        "confidence": "verified",
        "source": "Launchbot video placement registry + Intercom Articles API",
        "scope": {
            **scope,
            "intercom_article_id": article_id,
            "current_article_state": payload.get("state"),
        },
        "caveat": "Draft-only video-slot update. It does not rewrite article copy or publish the article.",
        "_updated_body": patch["updated_body"],
    }


@mcp.tool()
def preview_help_article_video_update(article_hint: str, loom_url: str, slot_id: str = "") -> dict[str, Any]:
    """Preview a registered help article Loom video-slot replacement. No mutation."""

    scope = _scope(article_hint, slot_id, False)
    try:
        result = _preview_patch(article_hint, loom_url, slot_id, False)
    except LaunchbotHelpArticleError as error:
        return _blocked(str(error), "Launchbot video placement registry + Intercom Articles API", scope)
    result.pop("_updated_body", None)
    return result


@mcp.tool()
def create_help_article_video_update_draft(
    article_hint: str,
    loom_url: str,
    slot_id: str = "",
    approval_marker: str = "",
) -> dict[str, Any]:
    """Create an Intercom draft by applying the same checked registered Loom video-slot patch."""

    scope = _scope(article_hint, slot_id, True)
    marker = str(approval_marker or "").strip().lower()
    if not any(term in marker for term in ("draft it", "draft", "approve", "approved")):
        return _blocked("Missing approval marker. The Slack user must confirm with draft it before mutation.", "Launchbot approval gate", scope)
    try:
        preview = _preview_patch(article_hint, loom_url, slot_id, True)
        article_id = str(preview["article"]["intercom_article_id"])
        payload = _update_intercom_article_draft(article_id, preview["_updated_body"])
    except LaunchbotHelpArticleError as error:
        return _blocked(str(error), "Launchbot video placement registry + Intercom Articles API", scope)

    return {
        "intercom_article_id": article_id,
        "draft_url": _draft_url(article_id, payload),
        "article_state": "draft",
        "slot_id": preview["slot"]["slot_id"],
        "video_src": preview["new_video"],
        "will_publish": False,
        "confidence": "verified",
        "source": "Launchbot video placement registry + Intercom Articles API",
        "scope": {
            **scope,
            "intercom_article_id": article_id,
            "current_article_state": payload.get("state", "draft"),
        },
        "caveat": "Intercom draft updated only at the registered video slot. Public publishing remains human-owned.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
