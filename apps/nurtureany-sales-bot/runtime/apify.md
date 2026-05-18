# Apify Runtime

NurtureAny can use Apify as an explicit, approval-gated public social scraping helper for single-company enrichment.

## Server

- MCP server: `apify_nurtureany`
- Transport: hosted Streamable HTTP
- URL: `https://mcp.apify.com?tools=actors,docs`
- Auth: `APIFY_TOKEN` from the live profile dotenv/Secret Manager through `auth_metadata.type=bearer_env`
- Header shape: `Authorization: Bearer ${APIFY_TOKEN}` with `APIFY_TOKEN` exposed through the server `env` mapping

Do not commit `APIFY_TOKEN`, Actor datasets, cookies, session files, or raw exports.

## Tool Surface

The enabled Apify tool surface is intentionally generic and bounded:

- `search-actors`
- `fetch-actor-details`
- `call-actor`
- `get-actor-run`
- `get-actor-output`
- `search-apify-docs`
- `fetch-apify-docs`

Use Actor discovery to verify the current actor, input schema, maintainer, pricing, and public/no-cookie behavior before any run.

## Safety Rules

- Apify is explicit-run only. It is not part of the default company-enrichment waterfall.
- For enrichment, resolve exactly one scoped HubSpot company before using Apify.
- Confirm budget, actor choice, target URLs, and result limits before calling an Actor.
- Default to public pages only. Do not use login cookies, Sales Navigator, private groups, private profiles, or authenticated sessions unless a separate approved compliant path exists.
- LinkedIn, Instagram, and Facebook results remain manual-review evidence. Do not claim current-company or title verification from social scraping alone.
- Do not mutate HubSpot, send messages, or reveal bulk PII from Apify output.

## Skills

Use the dedicated skills for platform-specific actor selection and output contracts:

- `skills/apify-linkedin-scraper/SKILL.md`
- `skills/apify-instagram-scraper/SKILL.md`
- `skills/apify-facebook-scraper/SKILL.md`
