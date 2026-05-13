#!/usr/bin/env python3
"""Tavily-backed public company research MCP adapter for NurtureAny Sales Bot.

This server is read-only and HubSpot-scoped. It sends only safe company identity
fields to Tavily and returns reviewable public signals for game plans.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.public_research import MAX_RESEARCH_COMPANIES
from nurtureany_common.public_research import SCOPE_SOURCE
from nurtureany_common.public_research import TavilyError
from nurtureany_common.public_research import brand_parent_lookup_cost_report
from nurtureany_common.public_research import clean_company_input
from nurtureany_common.public_research import find_brand_parent_candidates as _find_brand_parent_candidates
from nurtureany_common.public_research import company_input_items
from nurtureany_common.public_research import research_cost_report
from nurtureany_common.public_research import research_public_company_signals as _research_public_company_signals
from nurtureany_common.scoped_company import scoped_company_error as _shared_scoped_company_error
from nurtureany_common.responses import blocked_response


mcp = FastMCP(
    "public_research_nurtureany",
    instructions=(
        "Read-only Tavily public company research for scoped NurtureAny HubSpot companies. "
        "Never mutate HubSpot and never scrape social/gated pages."
    ),
)


def _token() -> str:
    token = os.environ.get("TAVILY_API_KEY", "").strip()
    if not token:
        raise TavilyError("Missing TAVILY_API_KEY.")
    return token


def _scope(slack_user_email: str, companies: Any, research_mode: str) -> dict[str, Any]:
    return {
        "caller_email": (slack_user_email or "").strip().lower(),
        "requested_company_count": len(company_input_items(companies)),
        "max_company_count": MAX_RESEARCH_COMPANIES,
        "research_mode": research_mode,
        "scope_source": SCOPE_SOURCE,
        "safety": "Only company_id, name, domain, and country are sent to Tavily.",
    }


def _brand_scope(slack_user_email: str, brand_name: str, country: str) -> dict[str, Any]:
    return {
        "caller_email": (slack_user_email or "").strip().lower(),
        "brand_name": str(brand_name or "").strip(),
        "country": str(country or "Singapore").strip() or "Singapore",
        "scope_source": "brand_parent_identity_lookup",
        "safety": (
            "Brand-parent lookup is identity resolution only. "
            "The bot must re-query scoped HubSpot target accounts before public news research."
        ),
    }


def _blocked(message: str, scope: dict[str, Any], mode: str) -> dict[str, Any]:
    return blocked_response(
        message,
        "Tavily public company research",
        scope,
        cost_report=research_cost_report([], message, mode),
        company_signals=[],
        source_evidence=[],
        game_plan_inputs=[],
        manual_check_items=[],
        missing_evidence=[message],
        will_mutate_hubspot=False,
    )


def _brand_blocked(message: str, scope: dict[str, Any], query_count: int = 0) -> dict[str, Any]:
    return blocked_response(
        message,
        "Tavily brand-parent identity lookup",
        scope,
        cost_report=brand_parent_lookup_cost_report(scope.get("brand_name", ""), scope.get("country", "Singapore"), query_count, message),
        source_evidence=[],
        manual_check_items=[],
        missing_evidence=[message],
        will_mutate_hubspot=False,
    )


def _scoped_company_error(companies: list[dict[str, Any]]) -> str:
    return _shared_scoped_company_error(companies, "Tavily public company research", SCOPE_SOURCE, MAX_RESEARCH_COMPANIES)


@mcp.tool()
def research_public_company_signals(
    slack_user_email: str,
    companies: list[dict[str, Any]],
    research_mode: str = "standard",
    max_results_per_query: int | None = None,
) -> dict[str, Any]:
    """Research public web/news/company signals for scoped HubSpot companies."""

    company_items = company_input_items(companies)
    raw_companies = company_items[:MAX_RESEARCH_COMPANIES]
    scope = _scope(slack_user_email, company_items, research_mode)

    scoped_error = _scoped_company_error(raw_companies)
    if scoped_error:
        return _blocked(scoped_error, scope, research_mode)

    selected_companies = [clean_company_input(company) for company in raw_companies]
    selected_companies = [company for company in selected_companies if company["company_id"] and (company["name"] or company["domain"])]
    if not selected_companies:
        return _blocked("At least one scoped company_id plus company name or domain is required.", scope, research_mode)

    try:
        token = _token()
    except TavilyError as error:
        return _blocked(str(error), scope, research_mode)

    try:
        result = _research_public_company_signals(selected_companies, token, research_mode, max_results_per_query)
    except TavilyError as error:
        return _blocked(str(error), scope, research_mode)

    return {
        **result,
        "source": "Tavily Search and Extract public company research",
        "scope": scope,
        "requested_company_count": len(company_items),
        "returned_company_count": len(result.get("answer", [])),
        "truncated": len(company_items) > MAX_RESEARCH_COMPANIES,
    }


@mcp.tool()
def find_brand_parent_candidates(
    slack_user_email: str,
    brand_name: str,
    country: str = "Singapore",
    max_results_per_query: int | None = None,
) -> dict[str, Any]:
    """Find public parent/group names for an unresolved brand before HubSpot re-query.

    This tool is identity lookup only. It does not make the brand scoped and does
    not authorize public news research. Re-query HubSpot target accounts with
    the returned parent/group candidates before continuing.
    """

    scope = _brand_scope(slack_user_email, brand_name, country)
    cleaned_brand = str(brand_name or "").strip()
    if not cleaned_brand:
        return _brand_blocked("brand_name is required for brand-parent identity lookup.", scope)

    try:
        token = _token()
    except TavilyError as error:
        return _brand_blocked(str(error), scope)

    try:
        result = _find_brand_parent_candidates(cleaned_brand, token, country, max_results_per_query)
    except TavilyError as error:
        return _brand_blocked(str(error), scope)

    return {
        **result,
        "source": "Tavily Search public brand-parent identity lookup",
        "scope": scope,
        "will_mutate_hubspot": False,
    }


if __name__ == "__main__":
    mcp.run("stdio")
