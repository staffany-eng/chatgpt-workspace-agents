#!/usr/bin/env python3
"""Guarded Slack-thread to Jira Product Discovery intake MCP adapter for Launchbot."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

import launchbot_feature_intake_core as core


CONFIRMATION_PHRASES = core.CONFIRMATION_PHRASES


mcp = FastMCP(
    "launchbot_feature_intake",
    instructions=(
        "Guarded Launchbot adapter that reads bounded Slack thread context with "
        "SLACK_BOT_TOKEN and creates Jira Product Discovery KER ideas only after "
        "explicit confirmation. Required confirmation is create intake. "
        "It never sends Slack messages, comments on Jira, "
        "transitions Jira issues, or persists raw Slack transcripts."
    ),
)


@mcp.tool()
def preview_feature_intake_from_slack_thread(
    channel_id: str = "",
    thread_ts: str = "",
    message_ts: str = "",
    slack_permalink: str = "",
    summary_override: str = "",
) -> dict[str, Any]:
    """Preview a Jira Product Discovery KER intake from bounded Slack thread context. No mutation."""

    return core.preview_feature_intake_from_slack_thread(channel_id, thread_ts, message_ts, slack_permalink, summary_override)


@mcp.tool()
def create_feature_intake_from_slack_thread(
    channel_id: str = "",
    thread_ts: str = "",
    message_ts: str = "",
    slack_permalink: str = "",
    summary_override: str = "",
    confirmation: str = "",
) -> dict[str, Any]:
    """Create one KER idea from Slack context after explicit confirmation."""

    return core.create_feature_intake_from_slack_thread(
        channel_id,
        thread_ts,
        message_ts,
        slack_permalink,
        summary_override,
        confirmation,
    )


if __name__ == "__main__":
    mcp.run("stdio")
