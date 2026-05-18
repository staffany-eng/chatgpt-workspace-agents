#!/usr/bin/env python3
"""Direct store review MCP adapter for PSM Ops Bot."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env
from store_reviews_core import (
    confirm_store_review_identity as _confirm_store_review_identity,
    draft_store_review_reply as _draft_store_review_reply,
    get_store_review as _get_store_review,
    list_store_review_apps as _list_store_review_apps,
    list_store_reviews as _list_store_reviews,
    suggest_store_review_identity_candidates as _suggest_store_review_identity_candidates,
)


load_profile_env()

mcp = FastMCP(
    "psm_store_reviews",
    instructions=(
        "Direct Google Play Developer API and App Store Connect review access for PSM Ops Bot. "
        "Use store APIs as review truth, Slack as the triage surface, and do not publish public "
        "store replies in V1."
    ),
)


@mcp.tool()
def list_store_review_apps() -> dict[str, Any]:
    """List configured direct store review apps and credential expectations."""

    return _list_store_review_apps()


@mcp.tool()
def list_store_reviews(
    store: str = "",
    app_ref: str = "",
    limit: int = 20,
    page_token: str = "",
    lookback_days: int = 7,
) -> dict[str, Any]:
    """List recent App Store / Google Play reviews using direct store APIs."""

    return _list_store_reviews(
        store=store,
        app_ref=app_ref,
        limit=limit,
        page_token=page_token,
        lookback_days=lookback_days,
    )


@mcp.tool()
def get_store_review(store: str, review_id: str, app_ref: str = "") -> dict[str, Any]:
    """Fetch one canonical store review from Google Play or App Store Connect."""

    return _get_store_review(store=store, review_id=review_id, app_ref=app_ref)


@mcp.tool()
def draft_store_review_reply(review: dict[str, Any] | None = None, issue_summary: str = "") -> dict[str, Any]:
    """Draft a privacy-safe public store reply for human review only."""

    return _draft_store_review_reply(review=review, issue_summary=issue_summary)


@mcp.tool()
def suggest_store_review_identity_candidates(
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
    """Suggest customer/contact candidates from private support follow-up details."""

    return _suggest_store_review_identity_candidates(
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
def confirm_store_review_identity(
    review: dict[str, Any] | None = None,
    review_key: str = "",
    store: str = "",
    app_ref: str = "",
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

    return _confirm_store_review_identity(
        review=review,
        review_key=review_key,
        store=store,
        app_ref=app_ref,
        review_id=review_id,
        customer_key=customer_key,
        customer_name=customer_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        confirmation_text=confirmation_text,
        confirmed_by=confirmed_by,
        state_path=state_path,
    )


if __name__ == "__main__":
    mcp.run("stdio")
