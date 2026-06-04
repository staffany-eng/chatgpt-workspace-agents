# Proposal: Add PSM Ops Geocode File Input

## Summary

Allow PSM Ops Bot to geocode address rows from attached Slack `.csv` or `.tsv` files when a tagged geocode request references the attachment.

## Problem

The current Google geocode workflow only accepts address rows extracted from Slack message text. Users can attach a TSV/CSV with an `address` column, but the bot asks them to paste the addresses because the MCP does not fetch and parse attached files.

## Goals

- Download CSV/TSV attachments from the current Slack thread using the bot token.
- Parse an `address` column deterministically with Python CSV parsing.
- Preserve optional label/customer/outlet/source metadata where present.
- Reuse the existing geocode and Slack TSV output path.
- Keep the 25-address limit, no raw coordinate Slack replies, and no address-row storage.

## Non-Goals

- No Excel/XLSX ingestion.
- No file ingestion for non-geocode workflows.
- No persistence of uploaded input files or geocode rows.
