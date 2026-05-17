#!/usr/bin/env python3
"""AppFollow review MCP adapter for PSM Ops Bot."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from appfollow_reviews_core import (
    confirm_appfollow_review_identity as _confirm_appfollow_review_identity,
    draft_appfollow_reply as _draft_appfollow_reply,
    get_appfollow_review as _get_appfollow_review,
    list_appfollow_apps as _list_appfollow_apps,
    publish_appfollow_reply_after_approval as _publish_appfollow_reply_after_approval,
    suggest_appfollow_review_identity_candidates as _suggest_appfollow_review_identity_candidates,
    tag_appfollow_review as _tag_appfollow_review,
)
from profile_env import load_profile_env


load_profile_env()

mcp = FastMCP(
    "psm_appfollow",
    instructions=(
        "Event-driven AppFollow review access for PSM Ops Bot. Use Slack review alerts "
        "as the trigger, AppFollow as review metadata/tag/reply truth, and never publish "
        "public replies without explicit same-thread approval."
    ),
)


@mcp.tool()
def list_appfollow_apps() -> dict[str, Any]:
    """List AppFollow account apps/collections to verify StaffAny app access."""

    return _list_appfollow_apps()


@mcp.tool()
def get_appfollow_review(
    ext_id: str = "",
    collection_name: str = "",
    review_id: str = "",
    country: str = "",
    lang: str = "",
    from_date: str = "",
    to_date: str = "",
    last_modified: str = "",
    page: int = 1,
) -> dict[str, Any]:
    """Fetch a canonical AppFollow review with a bounded query."""

    return _get_appfollow_review(
        ext_id=ext_id,
        collection_name=collection_name,
        review_id=review_id,
        country=country,
        lang=lang,
        from_date=from_date,
        to_date=to_date,
        last_modified=last_modified,
        page=page,
    )


@mcp.tool()
def tag_appfollow_review(
    ext_id: str,
    review_id: str,
    tags: str | list[str],
    apps_id: int | str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Preview or apply AppFollow review tags. Dry-run is default."""

    return _tag_appfollow_review(ext_id=ext_id, review_id=review_id, tags=tags, apps_id=apps_id, apply=apply)


@mcp.tool()
def draft_appfollow_reply(review: dict[str, Any] | None = None, issue_summary: str = "") -> dict[str, Any]:
    """Draft a public review reply for human approval."""

    return _draft_appfollow_reply(review=review, issue_summary=issue_summary)


@mcp.tool()
def suggest_appfollow_review_identity_candidates(
    review: dict[str, Any] | None = None,
    private_claim: dict[str, Any] | None = None,
    c360_candidates: list[Any] | None = None,
    email: str = "",
    phone: str = "",
    company_or_outlet: str = "",
    reviewer_nickname: str = "",
    review_text: str = "",
    slack_thread_url: str = "",
    state_path: str = "",
) -> dict[str, Any]:
    """Suggest StaffAny customer/contact candidates from private support follow-up details."""

    return _suggest_appfollow_review_identity_candidates(
        review=review,
        private_claim=private_claim,
        c360_candidates=c360_candidates,
        email=email,
        phone=phone,
        company_or_outlet=company_or_outlet,
        reviewer_nickname=reviewer_nickname,
        review_text=review_text,
        slack_thread_url=slack_thread_url,
        state_path=state_path,
    )


@mcp.tool()
def confirm_appfollow_review_identity(
    review: dict[str, Any] | None = None,
    review_key: str = "",
    store: str = "",
    ext_id: str = "",
    review_id: str = "",
    customer_key: str = "",
    customer_name: str = "",
    contact_email: str = "",
    contact_phone: str = "",
    confirmation_text: str = "",
    confirmed_by: str = "",
    state_path: str = "",
) -> dict[str, Any]:
    """Persist a human-confirmed review-to-customer/contact mapping in runtime state."""

    return _confirm_appfollow_review_identity(
        review=review,
        review_key=review_key,
        store=store,
        ext_id=ext_id,
        review_id=review_id,
        customer_key=customer_key,
        customer_name=customer_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        confirmation_text=confirmation_text,
        confirmed_by=confirmed_by,
        state_path=state_path,
    )


@mcp.tool()
def publish_appfollow_reply_after_approval(
    ext_id: str,
    review_id: str,
    answer_text: str,
    approval_text: str,
    login: str = "",
) -> dict[str, Any]:
    """Publish a public AppFollow review reply only after same-thread approval."""

    return _publish_appfollow_reply_after_approval(
        ext_id=ext_id,
        review_id=review_id,
        answer_text=answer_text,
        approval_text=approval_text,
        login=login,
    )


if __name__ == "__main__":
    mcp.run("stdio")
