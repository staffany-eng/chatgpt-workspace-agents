#!/usr/bin/env python3
"""Minimal Launch Superpower Bot E2E runner.

This runner exists because the original vk-super-productivity source checkout is
not present on Da Ta Hermz. It exercises the same external surfaces from the
handoff: versioned article artifact, Google Doc review draft, Slack review post,
and Intercom draft creation.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error, parse, request


DEFAULT_CHANNEL_ID = "C01D9TLLLAJ"
DEFAULT_PARENT_COLLECTION_ID = "19487848"
DEFAULT_AUTHOR_ID = "3374597"
DEFAULT_INTERCOM_APP_ID = "y12ertqm"


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def env_value(*names: str, required: bool = True) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    if required:
        fail(f"missing-env:{'|'.join(names)}")
    return ""


def api_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=60) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        fail(f"http-error:{method}:{url}:{exc.code}:{detail[:500]}")
    except error.URLError as exc:
        fail(f"url-error:{method}:{url}:{exc.reason}")
    raise AssertionError("unreachable")


def google_access_token() -> str:
    raw_json = env_value(
        "LAUNCH_GOOGLE_AUTH_JSON",
        "LAUNCH_STEP3_GOOGLE_SERVICE_ACCOUNT_JSON",
        required=False,
    )
    auth_file = os.environ.get("GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE")
    if raw_json:
        creds = json.loads(raw_json)
    elif auth_file:
        creds = json.loads(Path(auth_file).read_text(encoding="utf-8"))
    else:
        fail("missing-env:LAUNCH_GOOGLE_AUTH_JSON|GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE")

    if creds.get("type") != "authorized_user":
        fail("google-auth:only-authorized-user-json-supported-by-this-runner")

    form = parse.urlencode(
        {
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = request.Request("https://oauth2.googleapis.com/token", data=form, method="POST")
    with request.urlopen(req, timeout=60) as res:
        token = json.loads(res.read().decode("utf-8"))
    return token["access_token"]


def article_markdown(issue: str, version: str) -> str:
    title = f"Managing ClubAny brands and perks ({issue} {version})"
    return f"""# {title}

**Contents of this article are applicable to the following users**
Tier: Growth, Scale
Product: StaffAny
Platform: Web
Access Level: Owner

ClubAny lets you publish employee perks under branded business profiles. As an Owner, you can create the brands your organisation presents, add perks under each brand, and control which perks appear in the staff mobile catalogue.

**This guide will cover how to:**

1. Create and manage a brand
2. Add and manage perks under a brand
3. Understand catalogue visibility
4. FAQ

## Managing Brands

A brand is the business profile. It groups related perks under one identity for your staff to browse.

### Adding Brands

1. Open **ClubAny** in the StaffAny web portal.
2. Select **Brands**.
3. Click **Add Brand**.
4. Enter the brand name, upload a logo, and fill in the brand description.
5. Set the brand status to **Active** when ready.
6. Click **Save**.

[Screenshot placeholder: Brand creation form]

### Editing Brands

1. Open **ClubAny** and select **Brands**.
2. Click the brand you want to update.
3. Edit the brand details.
4. Click **Save**.

### Archiving / Unarchiving Brands

1. Open the brand details page.
2. Change the brand status to **Inactive** to hide it from the catalogue.
3. Change it back to **Active** when it is ready to appear again.

## Managing Perks

A perk sits under a brand and contains redeemable perk details. Staff see these details when browsing and redeeming perks in the mobile app.

### Adding Perks

1. Open **ClubAny** in the StaffAny web portal.
2. Select the brand that should contain the perk.
3. Click **Add Perk**.
4. Enter the perk name, description, terms, and redemption instructions.
5. Set the perk status to **Active**.
6. Click **Save**.

[Screenshot placeholder: Perk creation form]

### Editing Perks

1. Open the brand that contains the perk.
2. Select the perk you want to update.
3. Edit the perk details.
4. Click **Save**.

### Archiving / Unarchiving Perks

1. Open the perk details page.
2. Change the perk status to **Inactive** to hide it from staff.
3. Change it back to **Active** when it is ready for redemption.

## Catalogue Visibility

An active brand still does not appear in the mobile catalogue until it has at least one active perk. If a brand is missing from the catalogue, check that the brand is active and that at least one perk under it is also active.

## FAQ

**Q: Why is my active brand not showing in the mobile catalogue?**

A: The brand needs at least one active perk before it appears to staff.

**Q: Can staff redeem perks from the web portal?**

A: No. Owners manage brands and perks on Web, while staff discover and redeem perks from Mobile.

**Q: What happens when I archive a perk?**

A: Staff can no longer see or redeem that perk, but the setup remains available for future reactivation.
"""


def article_html(markdown: str, *, omit_top_heading: bool = False) -> str:
    lines = markdown.splitlines()
    html_lines: list[str] = []
    in_ol = False
    top_heading_omitted = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            continue
        numbered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if numbered:
            if not in_ol:
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"<li>{inline_html(numbered.group(1))}</li>")
            continue
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False
        if stripped.startswith("# "):
            if omit_top_heading and not top_heading_omitted:
                top_heading_omitted = True
                continue
            html_lines.append(f"<h1>{inline_html(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{inline_html(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            html_lines.append(f"<h3>{inline_html(stripped[4:])}</h3>")
        elif stripped.startswith("[Screenshot placeholder:"):
            html_lines.append(f"<p><em>{html.escape(stripped)}</em></p>")
        else:
            html_lines.append(f"<p>{inline_html(stripped)}</p>")
    if in_ol:
        html_lines.append("</ol>")
    return "\n".join(html_lines)


def inline_html(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def write_artifacts(base_dir: Path, issue: str, version: str, markdown: str) -> dict[str, Any]:
    version_dir = base_dir / "step-1-help-article-trigger" / "issues" / issue / "versions" / version
    version_dir.mkdir(parents=True, exist_ok=True)
    title = markdown.splitlines()[0].removeprefix("# ").strip()
    article_path = version_dir / "owner-management.md"
    notes_path = version_dir / "internal-notes.md"
    manifest_path = version_dir / "manifest.json"
    article_path.write_text(markdown, encoding="utf-8")
    notes_path.write_text(
        "\n".join(
            [
                "# Internal Notes",
                "",
                "- Source of truth: Launch Superpower Bot packet and 2026-05-11 handoff.",
                "- Runtime source checkout: not present; runner used packet-backed article contract.",
                "- Key app packet: apps/launch-superpower-bot/.",
                "- Assumption: KER-1742 ClubAny management can use Vanessa's combined article target.",
                f"- Last verified issue/version: {issue}/{version}.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "issue": issue,
        "version": version,
        "generated_at": int(time.time()),
        "articles": [
            {
                "slug": "owner-management",
                "title": title,
                "markdown_path": str(article_path),
                "internal_notes_path": str(notes_path),
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def create_google_doc(title: str, markdown: str) -> str:
    token = google_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    doc = api_json(
        "POST",
        "https://docs.googleapis.com/v1/documents",
        headers=headers,
        payload={"title": title},
    )
    document_id = doc["documentId"]
    api_json(
        "POST",
        f"https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate",
        headers=headers,
        payload={"requests": [{"insertText": {"location": {"index": 1}, "text": markdown}}]},
    )
    return f"https://docs.google.com/document/d/{document_id}/edit"


def post_slack_review(channel_id: str, title: str, doc_url: str) -> tuple[str, str]:
    token = env_value("LAUNCH_STEP2_SLACK_BOT_TOKEN", "SLACK_BOT_TOKEN")
    payload = {
        "channel": channel_id,
        "text": (
            "Launchbot automation: review draft ready for approval.\n"
            f"Article: {title}\n"
            f"Google Doc: {doc_url}\n"
            "React with :white_check_mark: after review before publishing."
        ),
        "unfurl_links": False,
        "unfurl_media": False,
    }
    response = api_json(
        "POST",
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}"},
        payload=payload,
    )
    if response.get("error") == "not_in_channel":
        join_response = api_json(
            "POST",
            "https://slack.com/api/conversations.join",
            headers={"Authorization": f"Bearer {token}"},
            payload={"channel": channel_id},
        )
        if join_response.get("ok"):
            response = api_json(
                "POST",
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                payload=payload,
            )
    if not response.get("ok"):
        fail(f"slack:post-failed:{response.get('error')}")
    return response["channel"], response["ts"]


def intercom_direct_url(article_id: Any) -> str:
    if not article_id:
        return ""
    app_id = env_value("LAUNCH_STEP3_INTERCOM_APP_ID", required=False) or DEFAULT_INTERCOM_APP_ID
    return f"https://app.intercom.com/a/apps/{app_id}/articles/articles/{article_id}/show"


def create_intercom_draft(title: str, markdown: str) -> dict[str, Any]:
    token = env_value("LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN", "INTERCOM_ACCESS_TOKEN")
    parent_id = env_value("LAUNCH_STEP3_INTERCOM_STAGING_COLLECTION_ID", required=False) or DEFAULT_PARENT_COLLECTION_ID
    author_id = env_value("LAUNCH_STEP3_INTERCOM_AUTHOR_ID", required=False) or DEFAULT_AUTHOR_ID
    payload = {
        "title": title,
        "description": "Draft generated by Launchbot automation for review.",
        "body": article_html(markdown, omit_top_heading=True),
        "author_id": int(author_id),
        "state": "draft",
        "parent_id": int(parent_id),
        "parent_type": "collection",
    }
    article = api_json(
        "POST",
        "https://api.intercom.io/articles",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Intercom-Version": "2.11",
        },
        payload=payload,
    )
    return article


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", default="KER-1742")
    parser.add_argument("--version", default="v006")
    parser.add_argument("--summary", default="ClubAny brands, perks, and redemptions")
    parser.add_argument("--output-root", default=os.path.expanduser("~/launchbot-runs"))
    parser.add_argument("--channel-id", default=os.environ.get("LAUNCH_STEP2_SLACK_CHANNEL_ID", DEFAULT_CHANNEL_ID))
    parser.add_argument("--skip-slack", action="store_true")
    parser.add_argument("--skip-google-doc", action="store_true")
    parser.add_argument("--skip-intercom", action="store_true")
    args = parser.parse_args()

    output_root = Path(args.output_root)
    markdown = article_markdown(args.issue, args.version)
    manifest = write_artifacts(output_root, args.issue, args.version, markdown)
    article = manifest["articles"][0]
    title = article["title"]

    step2_dir = output_root / "step-2-google-docs-approval" / "issues" / args.issue / "versions" / args.version
    step2_dir.mkdir(parents=True, exist_ok=True)
    step3_dir = output_root / "step-3-intercom-publish" / "issues" / args.issue / "versions" / args.version
    step3_dir.mkdir(parents=True, exist_ok=True)

    google_doc_url = ""
    if not args.skip_google_doc:
        google_doc_url = create_google_doc(title, markdown)

    slack_channel = ""
    slack_ts = ""
    if not args.skip_slack:
        if not google_doc_url:
            fail("slack:requires-google-doc-url")
        slack_channel, slack_ts = post_slack_review(args.channel_id, title, google_doc_url)

    step2_manifest = {
        "issue": args.issue,
        "version": args.version,
        "article_slug": article["slug"],
        "google_doc_url": google_doc_url,
        "slack_channel": slack_channel,
        "slack_ts": slack_ts,
    }
    (step2_dir / "manifest.json").write_text(json.dumps(step2_manifest, indent=2) + "\n", encoding="utf-8")

    intercom_article = {}
    if not args.skip_intercom:
        intercom_article = create_intercom_draft(title, markdown)

    step3_manifest = {
        "issue": args.issue,
        "version": args.version,
        "article_slug": article["slug"],
        "intercom_article_id": intercom_article.get("id"),
        "intercom_url": intercom_article.get("url"),
        "intercom_direct_url": intercom_direct_url(intercom_article.get("id")),
        "intercom_state": intercom_article.get("state"),
        "intercom_parent_id": intercom_article.get("parent_id"),
    }
    (step3_dir / "manifest.json").write_text(json.dumps(step3_manifest, indent=2) + "\n", encoding="utf-8")

    result = {
        "status": "ok",
        "issue": args.issue,
        "version": args.version,
        "summary": args.summary,
        "step1_manifest": str(output_root / "step-1-help-article-trigger" / "issues" / args.issue / "versions" / args.version / "manifest.json"),
        "google_doc_url": google_doc_url,
        "slack_channel": slack_channel,
        "slack_ts": slack_ts,
        "intercom_article_id": intercom_article.get("id"),
        "intercom_url": intercom_article.get("url"),
        "intercom_direct_url": intercom_direct_url(intercom_article.get("id")),
        "intercom_state": intercom_article.get("state"),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
