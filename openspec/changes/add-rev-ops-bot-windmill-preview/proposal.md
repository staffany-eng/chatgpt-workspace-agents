# Proposal: Add RevOps Bot Windmill Approval Mode

## Summary

Add a RevOps Hermes bot source packet that can preflight, preview, and execute explicitly approved Billing Engine sub-deal and service-agreement requests by calling StaffAny Windmill RevOps scripts.

## Problem

BDOps wants a Slack bot that can reduce manual Retool work for billing flows. The safe boundary is to let Hermes collect and preview create-sub-deal requests through Windmill, then execute only after Windmill returns exact confirmation text and the Slack user provides that exact approval.

## Goals

- Add a `rev-ops-bot` Hermes app packet.
- Add a narrow Windmill MCP client for read/search, dry-run preview, and approval-gated execution.
- Force dry-run server-side in preview tools.
- Require exact confirmation text and approval metadata for execution tools.
- Document Slack behavior, Windmill variables, and direct-write boundaries.
- Add focused verification for the app packet and MCP core tests.

## Non-Goals

- No direct HubSpot, SignNow, Stripe, or Xendit access.
- No deployment script or production Slack smoke test in this change.
