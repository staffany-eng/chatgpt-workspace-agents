---
name: apify-instagram-scraper
description: Use when scraping or exporting public Instagram profile, post, hashtag, place, reel, mention, or comment data through Apify Actors, Apify API, or Apify MCP. Trigger for Instagram scraping, Instagram scraper, Apify Instagram, public Instagram data export, Instagram comments, Instagram profiles, or Instagram social listening.
---

# Apify Instagram Scraper

Use this NurtureAny standalone skill to collect public Instagram data with the `apify_nurtureany` MCP server. It is an explicit-run enrichment helper, not part of the default single-company waterfall.

## Preconditions

- Use only public Instagram URLs, usernames, hashtags, places, posts, reels, or comments.
- Require the configured `apify_nurtureany` MCP server. Use `APIFY_TOKEN` only from the runtime profile/Secret Manager as the MCP bearer token or as a fallback for manual API debugging.
- Never commit tokens, dataset exports with private data, cookies, session files, or `.env` files.
- Confirm scope, maximum results, and budget before large or paid runs. Start with a small dry run when the target or actor behavior is uncertain.
- Do not use login cookies or private-session scraping unless the user explicitly provides a compliant, approved path for that account and target.

## Actor Selection

Prefer Apify-maintained actors when they fit:

| Need | Actor | Notes |
| --- | --- | --- |
| General posts, profiles, places, hashtags, photos, comments | `apify/instagram-scraper` | Broad public Instagram scraper; supports URLs and search-style inputs. |
| Profile metadata only | `apify/instagram-profile-scraper` | Use when the task is profile enrichment rather than post/comment collection. |
| Dedicated post, hashtag, reel, mention tasks | Apify Store Instagram-specific actors | Verify current actor details and schema before running. |

Before a real run, fetch or open the actor's current Apify Store/API page and confirm:

- actor ID and maintainer;
- input schema and required field names;
- pricing and free-trial limits;
- output dataset shape;
- last modified date or issue status if reliability matters.

## MCP Setup

Configure Apify MCP in the runtime before using this skill:

```json
{
  "mcpServers": {
    "apify_nurtureany": {
      "url": "https://mcp.apify.com?tools=actors,docs",
      "headers": {
        "Authorization": "Bearer ${APIFY_TOKEN}"
      },
      "env": {
        "APIFY_TOKEN": "${APIFY_TOKEN}"
      },
      "auth_metadata": {
        "type": "bearer_env",
        "env": "APIFY_TOKEN"
      }
    }
  }
}
```

Prefer OAuth if the runtime supports it. If using a bearer token, keep it in the runtime config or secret store, not in this repo.

## Execution Pattern

Default path:

1. Use Apify MCP actor details or docs tools to fetch the current actor schema.
2. Build the smallest input that answers the user's request.
3. Call the selected actor only after confirming pricing/budget and explicit user approval for the bounded run.
4. Retrieve full dataset output if the preview is truncated.
5. Return a concise summary plus the dataset/run identifiers.

Fallback API path only when MCP is unavailable:

```bash
curl -sS \
  -H "Authorization: Bearer $APIFY_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.apify.com/v2/acts/apify~instagram-scraper/runs?waitForFinish=300" \
  -d '<actor-input-json>'
```

Then read items from the returned `defaultDatasetId`:

```bash
curl -sS \
  -H "Authorization: Bearer $APIFY_TOKEN" \
  "https://api.apify.com/v2/datasets/<datasetId>/items?clean=true&format=json"
```

Use `run-sync` or `waitForFinish` only for short, bounded runs. For larger runs, start asynchronously, poll the run status, then fetch the dataset.

## Input Guidance

- Normalize Instagram inputs before running: keep canonical URLs and record whether each target is a profile, post, reel, hashtag, or place.
- Cap results per target unless the user asks for a full export.
- For comments, prefer a post/reel URL and a comment limit.
- For monitoring, prefer saved Apify tasks or schedules rather than rerunning ad hoc large scrapes.
- Keep raw dataset exports out of git unless the user explicitly asks for a sanitized fixture.

## Output Contract

Report:

- actor ID and run ID;
- dataset ID and item count;
- requested scope and actual scope reached;
- pricing/budget notes if visible before or after the run;
- failures, blocked targets, or rate-limit warnings;
- a compact sample of normalized fields relevant to the user.

Do not claim the data is complete beyond what the actor run and public availability prove.

## Sources To Recheck

- Apify API overview: `https://apify.com/api`
- Apify MCP docs: `https://docs.apify.com/platform/integrations/mcp`
- Instagram Scraper actor: `https://apify.com/apify/instagram-scraper`
- Instagram Profile Scraper actor: `https://apify.com/apify/instagram-profile-scraper`
