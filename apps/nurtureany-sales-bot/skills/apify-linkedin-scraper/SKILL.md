---
name: apify-linkedin-scraper
description: Use when scraping or exporting public LinkedIn profile, company, post, feed, article, or engagement data through Apify Actors, Apify API, or Apify MCP. Trigger for LinkedIn scraping, LinkedIn scraper, Apify LinkedIn, LinkedIn profiles, LinkedIn company pages, LinkedIn posts, or public LinkedIn social listening.
---

# Apify LinkedIn Scraper

Use this NurtureAny standalone skill to collect public LinkedIn data with the `apify_nurtureany` MCP server. It is an explicit-run enrichment helper, not part of the default single-company waterfall.

## Preconditions

- Use only publicly visible LinkedIn pages, profiles, company pages, posts, feeds, articles, and engagement data.
- Require the configured `apify_nurtureany` MCP server. Use `APIFY_TOKEN` only from the runtime profile/Secret Manager as the MCP bearer token or as a fallback for manual API debugging.
- Never commit tokens, dataset exports with private data, cookies, session files, or `.env` files.
- Confirm scope, maximum results, actor maintainer, reliability, and budget before any paid run.
- Do not use LinkedIn login cookies, Sales Navigator sessions, private profiles, private groups, or account-authenticated scraping unless the user explicitly provides a compliant, approved path for that account and target.

## Actor Selection

As of the last check, LinkedIn actors found on Apify for profiles/posts/companies were community-maintained, not Apify-maintained. Treat LinkedIn actor choice as a runtime verification step.

Current candidate actors to evaluate:

| Need | Candidate actor | Notes |
| --- | --- | --- |
| Public profile enrichment | `thirdwatch/linkedin-profile-scraper` | Public profiles, no login/cookies; verify pricing, freshness, and schema before use. |
| Public profile enrichment alternatives | `agentx/linkedin-profile-scraper`, `artificially/linkedin-profile-scraper`, `alwaysprimedev/linkedin-profile-scraper` | Compare output fields, price, usage, and last modified date. |
| Public company pages | `artificially/linkedin-company-scraper` or another current Store actor | Verify supported URLs and schema before use. |
| Public posts/feed collection | current Store LinkedIn post scraper actors | Verify whether direct post URLs, profile URLs, company URLs, comments, and reactions are supported. |

Before a real run, fetch or open the actor's current Apify Store/API page and confirm:

- actor ID, developer, and whether it is community-maintained;
- input schema and required field names;
- whether login/cookies are required;
- pricing, subscription requirements, and free-trial limits;
- output dataset shape;
- last modified date, total users, monthly users, issue status, and reviews.

If there is no suitable actor with a clear public-data/no-cookie contract, stop and report the blocked condition instead of improvising with an unverified scraper.

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

1. Search/fetch actor details from Apify MCP for the exact LinkedIn data type.
2. Compare candidate actors against the preconditions and the user's requested fields.
3. Pick the lowest-scope actor and smallest bounded input.
4. Call the actor only after confirming pricing, no-cookie/public-data behavior, and explicit user approval for the bounded run.
5. Retrieve full dataset output if the preview is truncated.
6. Return a concise summary plus the dataset/run identifiers.

Fallback API path only when MCP is unavailable:

```bash
curl -sS \
  -H "Authorization: Bearer $APIFY_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "https://api.apify.com/v2/acts/thirdwatch~linkedin-profile-scraper/runs?waitForFinish=300" \
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

- Normalize LinkedIn inputs before running: keep canonical URLs and record whether each target is a person profile, company page, post, feed, or article.
- For profile enrichment, prefer explicit `/in/` URLs or usernames and cap profile count.
- For companies, prefer explicit `/company/` URLs and cap pages.
- For posts, prefer explicit company/profile feed sources and cap posts per source; use date filters when available.
- Treat personal contact fields as sensitive. Summarize aggregate findings unless the user explicitly needs row-level output and has a legitimate work purpose.
- Keep raw dataset exports out of git unless the user explicitly asks for a sanitized fixture.

## Output Contract

Report:

- actor ID, maintainer, and run ID;
- dataset ID and item count;
- requested scope and actual scope reached;
- pricing/budget notes if visible before or after the run;
- whether login/cookies were required or avoided;
- failures, blocked targets, or rate-limit warnings;
- a compact sample of normalized fields relevant to the user.

Do not claim the data is complete beyond what the actor run and public availability prove.

## Sources To Recheck

- Apify API overview: `https://apify.com/api`
- Apify MCP docs: `https://docs.apify.com/platform/integrations/mcp`
- LinkedIn candidate example: `https://apify.com/thirdwatch/linkedin-profile-scraper`
- Apify Store LinkedIn search: `https://apify.com/store?search=linkedin`
