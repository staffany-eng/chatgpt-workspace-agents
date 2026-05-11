"""Customer 360 route and URL helpers shared by NurtureAny adapters."""

from __future__ import annotations

import json
import os
import urllib.parse
from typing import Any

C360_COMPANY_URL_TEMPLATE_ENV = "NURTUREANY_C360_COMPANY_URL_TEMPLATE"
C360_ORG_URL_TEMPLATE_ENV = "NURTUREANY_C360_ORG_URL_TEMPLATE"
C360_ROUTE_KEY_BY_COMPANY_ID_ENV = "NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID"
DEFAULT_C360_COMPANY_URL_TEMPLATE = "https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}"
DEFAULT_C360_ORG_URL_TEMPLATE = (
    "https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}/orgs/{organisation_id}"
)
DEFAULT_C360_ROUTE_KEY_BY_COMPANY_ID = {
    "1991281569": "fei-siong-group",
}


def _configured_template(env_var: str, default: str) -> str:
    value = os.environ.get(env_var, "").strip()
    if not value or value in {f"${{{env_var}}}", f"${env_var}"}:
        return default
    return value


def c360_company_url_template() -> str:
    return _configured_template(C360_COMPANY_URL_TEMPLATE_ENV, DEFAULT_C360_COMPANY_URL_TEMPLATE)


def c360_org_url_template() -> str:
    return _configured_template(C360_ORG_URL_TEMPLATE_ENV, DEFAULT_C360_ORG_URL_TEMPLATE)


def c360_route_key_map() -> dict[str, str]:
    mappings = dict(DEFAULT_C360_ROUTE_KEY_BY_COMPANY_ID)
    raw = os.environ.get(C360_ROUTE_KEY_BY_COMPANY_ID_ENV, "").strip()
    if not raw:
        return mappings
    try:
        configured = json.loads(raw)
    except json.JSONDecodeError:
        return mappings
    if not isinstance(configured, dict):
        return mappings
    for company_id, route_key in configured.items():
        company_id_text = str(company_id or "").strip()
        route_key_text = str(route_key or "").strip()
        if company_id_text and route_key_text:
            mappings[company_id_text] = route_key_text
    return mappings


def customer360_route_key(
    hubspot_company_id: Any,
    company_name: Any = "",
    customer360_route_key: Any = "",
) -> str:
    explicit_route_key = str(customer360_route_key or "").strip()
    if explicit_route_key:
        return explicit_route_key

    company_id = str(hubspot_company_id or "").strip()
    if not company_id:
        return ""

    mapped_route_key = c360_route_key_map().get(company_id)
    if mapped_route_key:
        return mapped_route_key

    if not company_id.isdigit():
        return company_id

    return ""


def encode_url_value(value: Any) -> str:
    return urllib.parse.quote(str(value or "").strip(), safe="")


def render_c360_url(
    hubspot_company_id: Any,
    organisation_id: Any = "",
    customer360_route_key_value: Any = "",
    company_name: Any = "",
    **kwargs: Any,
) -> str:
    company_id = str(hubspot_company_id or "").strip()
    org_id = str(organisation_id or "").strip()
    explicit_route_key = kwargs.get("customer360_route_key", customer360_route_key_value)
    route_key = customer360_route_key(company_id, company_name, explicit_route_key)
    if not route_key:
        return ""

    values = {
        "customer360_route_key": encode_url_value(route_key),
        "hubspot_company_id": encode_url_value(route_key),
        "hubspot_numeric_company_id": encode_url_value(company_id),
        "organisation_id": encode_url_value(org_id),
    }
    template = c360_org_url_template() if org_id else c360_company_url_template()
    return template.format(**values)
