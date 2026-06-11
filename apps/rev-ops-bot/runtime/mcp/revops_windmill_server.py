#!/usr/bin/env python3
"""RevOps Windmill MCP adapter."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

import revops_windmill_core as core


mcp = FastMCP(
    "revops_windmill",
    instructions=(
        "RevOps Bot Windmill adapter. Provides Billing Engine main-deal search "
        "read-only create-sub-deal preflight, and create-sub-deal/service-agreement "
        "dry-run preview through Windmill. It can also apply explicitly approved "
        "HubSpot readiness updates and execute explicitly approved Billing Engine "
        "create-sub-deal/service-agreement requests."
    ),
)


@mcp.tool()
def check_windmill_revops_config() -> dict[str, Any]:
    """Check local Windmill configuration without printing secrets."""

    return core.check_windmill_revops_config()


@mcp.tool()
def search_billing_main_deals(
    search: str = "",
    stage_ids: list[str] | None = None,
    deal_motions: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search billing main deals through Windmill. Read-only."""

    return core.search_billing_main_deals(search, stage_ids, deal_motions, limit, offset)


@mcp.tool()
def preflight_create_sub_deal_request(request_json: str = "") -> dict[str, Any]:
    """Run read-only readiness checks before create-sub-deal preview."""

    return core.preflight_create_sub_deal_request_json(request_json)


@mcp.tool()
def preview_create_sub_deal_and_service_agreement(request_json: str = "") -> dict[str, Any]:
    """Preview create-sub-deal/service-agreement request. Forces dry_run=true."""

    return core.preview_create_sub_deal_and_service_agreement_json(request_json)


@mcp.tool()
def preview_preflight_updates(request_json: str = "") -> dict[str, Any]:
    """Preview approved HubSpot readiness updates without applying them."""

    return core.apply_preflight_updates_json(request_json, dry_run=True)


@mcp.tool()
def apply_approved_preflight_updates(request_json: str = "") -> dict[str, Any]:
    """Apply approved HubSpot readiness updates through Windmill."""

    return core.apply_preflight_updates_json(request_json, dry_run=False)


@mcp.tool()
def execute_approved_create_sub_deal_and_service_agreement(request_json: str = "") -> dict[str, Any]:
    """Execute approved create-sub-deal/service-agreement request through Windmill."""

    return core.execute_create_sub_deal_and_service_agreement_json(request_json)


@mcp.tool()
def preview_send_service_agreement(request_json: str = "") -> dict[str, Any]:
    """Preview send-service-agreement request. Forces dry_run=true."""

    return core.preview_send_service_agreement_json(request_json)


@mcp.tool()
def execute_approved_send_service_agreement(request_json: str = "") -> dict[str, Any]:
    """Execute approved send-service-agreement request through Windmill."""

    return core.execute_send_service_agreement_json(request_json)


if __name__ == "__main__":
    mcp.run("stdio")
