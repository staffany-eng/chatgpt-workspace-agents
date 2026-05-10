# Known-Area Near-Me Runtime

NurtureAny answers `I am here, who can I say hi to?` by snapping the user to a curated known area, then combining BigQuery outlet matches, C360 current customers, and Google Places live restaurant discovery.

This is not generic Google Search. Use Google Places Nearby Search for the live map refresh: `POST https://places.googleapis.com/v1/places:searchNearby`.

## Source Roles

- `known_areas`: curated config/table outside HubSpot. Examples: `sg_raffles_place`, `sg_vivocity`, `sg_plaza_singapura`, `sg_jewel_changi`.
- BigQuery `nurtureany_near_me_outlet_matches`: curated outlet/account memory layer. It stores place/account match state and points to HubSpot Company IDs when matched.
- Google Places: live discovery/enrichment only. Google-only restaurants are candidates, not confirmed accounts.
- BigQuery/C360: current-customer coverage from StaffAny geofenced sections and C360 live/customer company mapping.
- HubSpot Company: CRM context only when the row has `hubspot_company_id`; no HubSpot custom object is required.
- Customer 360 URL templates: current-customer output links use `NURTUREANY_C360_COMPANY_URL_TEMPLATE` and `NURTUREANY_C360_ORG_URL_TEMPLATE`, defaulting to `https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}` and `https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}/orgs/{organisation_id}`.
- Customer 360 route keys: render links from `customer360_route_key`, not raw numeric HubSpot IDs. `NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID` can provide a JSON map for known Customer 360 routes, with Fei Siong defaulting to `{"1991281569":"fei-siong-group"}`. Existing templates that still use `{hubspot_company_id}` receive the Customer 360 route key for compatibility.

## Runtime Flow

1. Resolve user location from a Google Maps link, shared lat/lng, or known area name.
2. Snap to nearest `known_area`; reuse its center and radius for the rest of the run.
3. Build and run the BigQuery outlet-match query for `area_id=<known_area.area_id>`.
4. Run Google Places refresh for restaurants around the known area center/radius, requesting only `places.id`, `places.displayName`, `places.formattedAddress`, `places.location`, and `places.googleMapsUri`.
5. Build and run the bounded C360 query through `staffany_bigquery.execute_sql_readonly`.
6. Merge account-level results:
   - dedupe by `google_place_id`, then `hubspot_company_id`, then `organisation_id`
   - preserve multiple outlet matches under one Company
   - keep nearest outlet/section, nearest distance, owner snapshot, account status, match confidence, C360 usage status, deal stage/end date, `c360_url` for current customers, and source flags
7. Return Slack output with customers first, then prospects, then Google-only live candidates.

## Outlet Match Query Contract

Use `build_near_me_outlet_matches_query`, then execute the returned SQL with `staffany_bigquery.execute_sql_readonly`.

Default table:

```text
staffany-warehouse.analytics.nurtureany_near_me_outlet_matches
```

Override with `NURTUREANY_OUTLET_MATCHES_TABLE` only if the table is moved.

The query must:

- filter by `area_id`
- exclude `match_status='rejected'`
- return only curated rows already present in BigQuery
- compute distance from the known-area center when outlet lat/lng exists
- not mutate HubSpot or BigQuery

## C360 Query Contract

Use `build_near_me_c360_customer_query`, then execute the returned SQL with `staffany_bigquery.execute_sql_readonly`.

The query must:

- source geofence coordinates from `kraken_rds.Locations`
- normalize swapped latitude/longitude defensively
- join `analytics.dim_sections` and exclude `isarchived` sections
- join `analytics.dim_org_section` for section/org context
- join `analytics.fct_deal_org_company` as the C360 live/customer layer
- left join `analytics.fct_company_org_mrr` only for optional MRR enrichment
- collapse to one row per `organisation_id`
- never query or expose person GPS, clock records, or raw employee location rows

`fct_company_org_mrr` is too strict as the main customer filter. Do not use it as the primary current-customer layer.

## Ranking

1. Confirmed outlet match plus current customer.
2. C360 current customer without stored outlet match.
3. Confirmed outlet match prospect.
4. Candidate outlet match.
5. Google Places live candidate, review needed.

Current/open selected deal ranks above past selected deal. Past selected deal remains visible with a caveat instead of being silently dropped.

## Current-Customer Links

Every current-customer item returned by `merge_near_me_sources` must include `c360_url` when a Customer 360 route key can be resolved. Use the org drilldown URL when both route key and `organisation_id` exist; otherwise use the company URL. If a current-customer item lacks a resolvable route key, keep it visible, set/keep `Confidence: needs-check`, and include the caveat `C360 link missing because Customer 360 route key was unavailable.`

## Storage

BigQuery `nurtureany_near_me_outlet_matches` stores curated matches only:

- `outlet_match_id`
- `area_id`
- `area_name`
- `outlet_name`
- `google_place_id`
- `formatted_address`
- `latitude`
- `longitude`
- `google_maps_uri`
- `hubspot_company_id`
- `hubspot_company_name`
- `hubspot_owner_id`
- `organisation_id`
- `match_status`: `confirmed`, `candidate`, or `rejected`
- `account_status`: `customer`, `prospect`, or `unknown`
- `confidence`
- `source`
- `source_note`
- `last_checked_at`
- `created_at`
- `updated_at`

DDL lives at `runtime/sql/near-me-outlet-matches.sql`.

Do not store every Google restaurant permanently. Google Places refresh output stays as live `candidate` data unless a review/approval workflow promotes it to the BigQuery table. Storage policy value: `live_candidate_only_until_review_approval`.

## MCP Tools

Server: `near_me_nurtureany`

- `resolve_known_area_for_near_me`: parse location text/lat-lng and return nearest known area.
- `build_near_me_outlet_matches_query`: return the bounded outlet-match SQL for BigQuery MCP execution.
- `refresh_google_places_for_known_area`: live Google Places restaurant refresh for the area.
- `build_near_me_c360_customer_query`: return the bounded C360 SQL for BigQuery MCP execution.
- `merge_near_me_sources`: merge BigQuery outlet matches, C360 rows, and Google Places candidates.

All tools are read-only. BigQuery outlet-match writes require a separate review/admin workflow. HubSpot writes are not part of this near-me V1.

## Output Shape

Plain Slack answer:

```text
Answer: You are near Raffles Place.

Customers nearby:
1. <company/outlet linked to c360_url> - customer, owner: <owner>, <distance>, <reason>

Prospects nearby:
2. <company/outlet> - prospect, owner: <owner>, <distance>, <reason>

Live candidates from Google Places:
3. <restaurant> - candidate, review needed

Source: BigQuery outlet_matches + C360 BigQuery + Google Places
Scope: known_area=sg_raffles_place, radius=1000m
Confidence: needs-check
Caveat: Google-only restaurants are not confirmed accounts. Past selected deals are marked.
```
