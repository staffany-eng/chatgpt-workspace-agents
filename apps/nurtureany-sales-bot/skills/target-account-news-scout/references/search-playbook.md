# Search Playbook

Use this file when the agent needs query patterns, source priorities, and relevance rules for a scoped NurtureAny target account.

## Search Order

1. Official company website and newsroom
2. Reputable news coverage
3. Partner announcements
4. Official social channels when clearly attributable

HubSpot remains the account-scope source of truth. Public sources provide outreach angles only; they do not override HubSpot ownership, target-account membership, current tools, contact coverage, renewal timing, follow-up activity, or customer/prospect status.

## Base Queries

Start with the smallest set that can identify the right company:

- `"<company name>" official site`
- `"<company name>" <industry> <country>`
- `site:<domain> news OR press OR blog`

Then move into recent signal discovery:

- `"<company name>" announcement OR launch OR launched`
- `"<company name>" partnership OR partners`
- `"<company name>" hiring OR expansion OR office`
- `"<company name>" CEO OR leadership OR appoints`
- `"<company name>" funding OR investment OR raises`
- `"<company name>" award OR recognition OR customer story`

If a persona is provided, bias the search:

- For `HR`: add `hiring`, `people`, `talent`, `culture`, `workforce`
- For `CEO`: add `strategy`, `expansion`, `growth`, `partnership`, `funding`
- For generic `decision-maker`: add `operations`, `transformation`, `launch`, `customer`

## Social Add-On

Only use social sources when the official handle is explicit or clearly linked from the company site.

- `site:instagram.com "<company name>"`
- `site:facebook.com "<company name>"`

Prefer posts that announce:

- launches
- events
- hiring momentum
- partnerships
- market expansion

Social and gated sources are manual-check only unless an approved official API is available. Do not scrape LinkedIn, Instagram, TikTok, Facebook, Google Maps web pages, or other gated/social surfaces.

## Relevance Rules

Prefer:

- content from the last 30 to 60 days
- official company or partner announcements
- items that create a natural reason to reach out now
- items tied to a likely business initiative

Avoid:

- listicles with no direct company event
- syndicated duplicates when the original is available
- content without a date
- scraping behind logins or access walls

## Signal Classification Hints

- `funding`: investment, capital raise, acquisition financing
- `leadership`: new executive, promotion, restructuring, board changes
- `hiring`: growth hiring, talent push, team build-out
- `product`: launch, release, feature rollout, integration
- `brand-buzz`: awards, campaign buzz, public brand momentum
- `news`: anything relevant that does not cleanly fit the categories above
