"""Scoped HubSpot company validation shared by enrichment adapters."""

from __future__ import annotations

from typing import Any


DEFAULT_SCOPE_SOURCE = "hubspot_nurtureany"


def is_scoped_hubspot_company(company: dict[str, Any], scope_source: str = DEFAULT_SCOPE_SOURCE) -> bool:
    company_id = str(company.get("company_id") or company.get("id") or "").strip()
    if not company_id:
        return False
    return company.get("hubspot_scoped") is True or str(company.get("scope_source") or "") == scope_source


def scoped_company_error(
    companies: list[dict[str, Any]],
    source_label: str,
    scope_source: str = DEFAULT_SCOPE_SOURCE,
    max_companies: int | None = None,
) -> str:
    inspected = companies[:max_companies] if max_companies is not None else companies
    unscoped = [
        str(index + 1)
        for index, company in enumerate(inspected)
        if not isinstance(company, dict) or not is_scoped_hubspot_company(company, scope_source)
    ]
    if not unscoped:
        return ""
    return (
        f"{source_label} requires scoped HubSpot company inputs from NurtureAny "
        f"with company_id and scope_source={scope_source}; unscoped input positions: {', '.join(unscoped)}."
    )
