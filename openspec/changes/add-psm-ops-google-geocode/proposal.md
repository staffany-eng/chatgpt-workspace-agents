# Proposal: Add PSM Ops Google Geocode Capability

## Summary

Add a bounded Google Geocoding capability to PSM Ops Bot so tagged Slack requests can return latitude/longitude rows for explicit addresses.

## Problem

PSM Ops users may paste address lists in Slack and need latitude/longitude for downstream operational work. The Google Geocoding API key is already stored outside the repo under `~/.staffany/google-geocode/credentials.json`, but PSM Ops Bot has no durable runtime surface that can read that credential and geocode Slack-provided addresses.

## Goals

- Add a narrow `psm_google_geocode` MCP server.
- Read the API key from runtime-only env or credential file paths.
- Return address rows with latitude, longitude, status, formatted address, and place ID.
- Document Slack behavior and safety boundaries.
- Wire manifest, config template, profile inventory, health checks, and verifier checks.

## Non-Goals

- No Slack file upload or Google Sheets creation.
- No storage of address rows or geocoding history.
- No geocoding of customer names or vague location hints.
