#!/usr/bin/env python3
"""Read-only weekly support-watch MCP adapter for Launchbot."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

import launchbot_support_watch_core as core


mcp = FastMCP(
    "launchbot_support_watch",
    instructions=(
        "Read-only Launchbot support-watch preview adapter. It queries BigQuery-backed "
        "Intercom conversations and optional WhatsApp support logs, clusters likely "
        "production regressions, dedupes against Slack duty-channel and EDT evidence, "
        "and traces likely Pantheon code causes. "
        "It never sends Slack messages, creates Jira/Linear tickets, assigns owners, "
        "tags engineers, or persists raw support transcripts."
    ),
)


@mcp.tool()
def preview_weekly_support_watch_report(
    window_start_iso: str = "",
    window_end_iso: str = "",
    lookback_days: int = core.DEFAULT_LOOKBACK_DAYS,
    max_tickets: int = core.DEFAULT_MAX_TICKETS,
    include_traces: bool = True,
) -> dict[str, Any]:
    """Preview the weekly support-watch report. No Slack post or ticket mutation."""

    return core.preview_weekly_support_watch_report(
        window_start_iso=window_start_iso,
        window_end_iso=window_end_iso,
        lookback_days=lookback_days,
        max_tickets=max_tickets,
        include_traces=include_traces,
    )


if __name__ == "__main__":
    mcp.run("stdio")
