---
name: metabase-usage-data
description: Query and interpret the cached Metabase card 2257 (All Usages Pivot) for feature adoption, account health, renewals, and RICE reach scoring. Load this skill whenever a user asks about feature usage rates, account health, customer renewals, or needs a data-backed RICE reach estimate.
tags: [metabase, usage, rice, account-health, renewal, feature-adoption, product-ops]
---

# Metabase Usage Data — Card 2257

## Data Source

**File:** `/home/leekaiyi/.hermes/profiles/launchbot/data/metabase_card_2257.json`
**Refreshed:** Daily at 01:00 UTC via cron job `metabase-card-2257-daily`
**Metabase URL:** https://metabase.staffany.com/question/2257-all-usages-pivot-filter
**Parameters:** `startweek=past1months`, no deal_end or country filter
**Current snapshot:** 613 accounts, 3 countries (SG 319, ID 221, MY 72)

## How to Read the File

```python
import json
with open('/home/leekaiyi/.hermes/profiles/launchbot/data/metabase_card_2257.json') as f:
    d = json.load(f)

cols = d['data']['data']['cols']   # column metadata list
rows = d['data']['data']['rows']   # list of value arrays (same order as cols)
col_names = [c['name'] for c in cols]

# Convert to list of dicts for easy access
records = [dict(zip(col_names, row)) for row in rows]
```

## Column Reference

### Identity & Account
| Col | Field | Type | Notes |
|-----|-------|------|-------|
| 0 | `Account_Health` | Text | `1-Red`, `2-Orange`, `3-Green`, `4-Green Plus` |
| 1 | `All_Usages_Score` | Int | Composite usage score (0–26+) |
| 2 | `organisation_name` | Text | StaffAny org name |
| 3 | `company_name` | Text | HubSpot deal/company name |
| 4 | `company_city` | Text | |
| 5 | `deal_id` | Text | HubSpot deal ID |
| 6 | `company_psm_name` | Text | PSM/CSM owner |
| 7 | `company_country` | Text | `Singapore`, `Indonesia`, `Malaysia` |
| 8 | `deal_start` | DateTime | Contract start |
| 9 | `deal_end` | DateTime | Contract end — use for renewal risk |
| 10 | `company_mrr` | Float | Monthly recurring revenue (SGD) |
| 11 | `activehc` | Int | Active headcount |

### Usage Metrics (feature adoption flags/scores)
| Col | Field | What it measures |
|-----|-------|-----------------|
| 12 | `0-avg_US` | Average usage score |
| 13 | `min_US` | Min usage score |
| 14 | `max_US` | Max usage score |
| 15 | `1-total_mass_grab_request` | Open shift / mass grab usage |
| 16 | `2-Scheduled_sections_pct` | % schedules using sections |
| 17 | `3-wage_set_pct` | % staff with wages set |
| 18 | `4-total_splh_records` | SPLH (sales per labor hour) records |
| 19 | `5-scheduleViewSwitched` | Schedule view switching events |
| 20 | `6-tsweek_locked` | Timesheet weeks locked |
| 21 | `7-total_unclean_timesheets` | Unclean timesheets (hygiene signal) |
| 22 | `8-ts_exported` | Timesheet exports |
| 23 | `9-customtscreated` | Custom timesheet columns created |
| 24 | `10-isusingtimeclocksidekick` | Bool: using Time Clock Sidekick |
| 25 | `11-isusing_ts_prevention` | Bool: using TS prevention |
| 26 | `12-approvedwma` | Approved WMA count |
| 27 | `13-shifttagsassigned` | Shift tags assigned |
| 28 | `14-shiftQuestionFilled` | Shift questions filled |
| 29 | `15-dayoffsapproved` | Day-offs approved |
| 30 | `16-leavebalance_checking` | Leave balance checks |
| 31 | `17-positive_leave_pct` | % positive leave balance |
| 32 | `18-defaultleavehour_pct` | % using default leave hours |
| 33 | `19-oiltaken` | OIL (off-in-lieu) taken |
| 34 | `20-payrun_participants_pct` | % staff in payrun |
| 35 | `21-bank_files_downloaded` | Bank file downloads |
| 36 | `22-payroll_report_exported` | Payroll report exports |
| 37 | `23-costlaborreport_view` | Cost/labour report views |
| 38 | `24-formulated_payitem_usage` | Formulated pay item usage |
| 39 | `25-claim_usage` | Claims usage |
| 40 | `26-EA_challenges_rewards` | EA challenges & rewards usage |

## Common Queries

### Feature adoption rate
```python
records = [dict(zip(col_names, row)) for row in rows]
total = len(records)
using = sum(1 for r in records if r['21-bank_files_downloaded'] and r['21-bank_files_downloaded'] > 0)
print(f"Bank file adoption: {using}/{total} = {using/total:.1%}")
```

### Account health breakdown
```python
from collections import Counter
health = Counter(r['Account_Health'] for r in records)
# Returns: {'2-Orange': 285, '1-Red': 157, '3-Green': 168, '4-Green Plus': 3}
```

### Renewals at risk (next 90 days)
```python
from datetime import datetime, timezone, timedelta
now = datetime.now(timezone.utc)
soon = now + timedelta(days=90)
at_risk = [r for r in records
           if r['deal_end']
           and now <= datetime.fromisoformat(r['deal_end']) <= soon]
```

### Filter by country
```python
sg = [r for r in records if r['company_country'] == 'Singapore']
id_ = [r for r in records if r['company_country'] == 'Indonesia']
my = [r for r in records if r['company_country'] == 'Malaysia']
```

## RICE Reach Scoring

Use this dataset as the **Reach denominator** for KER RICE estimates.

**Total active accounts (baseline):** 613
**By country:** SG=319, ID=221, MY=72
**By health tier:** Red=157, Orange=285, Green=168, Green Plus=3

### Reach estimation patterns

| Scenario | How to calculate |
|----------|-----------------|
| Feature targets all payroll users | Count `r['20-payrun_participants_pct'] > 0` |
| Feature targets scheduling users | Count `r['2-Scheduled_sections_pct'] > 0` |
| Feature targets timesheet users | Count `r['8-ts_exported'] > 0 or r['6-tsweek_locked'] > 0` |
| Feature targets SG only | `company_country == 'Singapore'` → 319 accounts |
| Feature targets high-risk renewals | `deal_end` within 90d → currently ~234 accounts |
| Feature targets Red/Orange accounts | Red+Orange → 442 accounts (72% of base) |
| Feature replaces a metric that's 0 | Count accounts where that metric is null/0 — those are the unreached |

### RICE Reach output format
When asked for RICE reach, output:
- **Reach:** N accounts (X% of 613 active)
- **Basis:** which column/filter was used
- **Caveat:** data is past-1-month snapshot, refreshed daily

## Pitfalls

- `null` values in usage columns mean "no activity" not "feature unavailable" — treat as 0 for adoption counts.
- `deal_end` dates in the past = expired deals — filter those out for active-base queries.
- `company_mrr = 0` records may be trials or internal — exclude from revenue-weighted analysis unless intentional.
- `organisation_name` ≠ `company_name` — org is StaffAny platform org, company is HubSpot entity.
- Data reflects **past 1 month** of activity. A feature unused last month may have been used before — this is recency, not lifetime adoption.
- Session token in the fetch script is tied to Abel's Metabase account. If cron fails with 401/403, the token needs refreshing in `.env`.
