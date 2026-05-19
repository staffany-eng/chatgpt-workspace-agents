---
name: apify-facebook-scraper
description: Use when scraping or exporting public Facebook page, profile, post, video, reel, comment, engagement, or page-contact data through Apify Actors, Apify API, or Apify MCP. Trigger for Facebook scraping, Facebook scraper, Apify Facebook, Facebook posts, Facebook comments, Facebook pages, or public Facebook social listening.
---

# Apify Facebook Scraper

Use this NurtureAny standalone skill to collect public Facebook data with the `apify_nurtureany` MCP server. It is an explicit-run enrichment helper, not part of the default single-company waterfall.

## Preconditions

- Use only publicly visible Facebook pages, profiles, posts, reels, videos, and comments.
- Require the configured `apify_nurtureany` MCP server. Use `APIFY_TOKEN` only from the runtime profile/Secret Manager as the MCP bearer token or as a fallback for manual API debugging.
- Never commit tokens, dataset exports with private data, cookies, session files, or `.env` files.
- Confirm scope, maximum results, and budget before large or paid runs. Start with a small dry run when the target or actor behavior is uncertain.
- Do not use user cookies, private groups, or account-authenticated scraping unless the user explicitly provides a compliant, approved path for that account and target.

## Actor Selection

Prefer Apify-maintained actors when they fit:

| Need | Actor | Notes |
| --- | --- | --- |
| Page or profile metadata, contacts, followers, likes, rating, ad status | `apify/facebook-pages-scraper` | Best first choice for page/profile facts. |
| Posts, captions, timestamps, reactions, media, shares, video transcripts | `apify/facebook-posts-scraper` | Best for public page/profile post history. |
| Comments and replies from post, photo, video, or reel URLs | `apify/facebook-comments-scraper` | Best for comment extraction. |

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
2. Select the narrow actor for the user's question rather than a broad scrape.
3. Build a bounded input with explicit URL list and result limits.
4. Call the actor only after confirming pricing/budget and explicit user approval for the bounded run.
5. Retrieve full dataset output if the preview is truncated.
6. Return a concise summary plus the dataset/run identifiers.

Fallback API path only when MCP is unavailable:

```bash
curl -sS \
  -H "Authorization: Bearer $APIFY_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.apify.com/v2/acts/apify~facebook-pages-scraper/runs?waitForFinish=300" \
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

- Normalize Facebook inputs before running: keep canonical URLs and record whether each target is a page/profile, post, video, reel, or photo.
- For pages/profiles, use the pages actor and avoid post/comment scraping unless needed.
- For posts, cap posts per source and use date filters when available.
- For comments, run against explicit post/reel/video/photo URLs and cap comment/reply counts.
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
- Facebook Pages Scraper actor: `https://apify.com/apify/facebook-pages-scraper`
- Facebook Posts Scraper actor: `https://apify.com/apify/facebook-posts-scraper`
- Facebook Comments Scraper actor: `https://apify.com/apify/facebook-comments-scraper`
