# StaffAny RBAC / Custom Access Levels Schema Notes

_Last updated: May 2026_

## Overview

StaffAny has two overlapping concepts for access level customisation:

1. System access levels: `employee`, `manager`, `owner`, `supervisor`. Stored as the `accessLevel` field in `OrgUserDetails`. These are enum values; the UI label-rename feature (`isaccesslevelrenamed` flag) has never been enabled in production.
2. RBAC permission groups: `RbacRoles` and `RbacRolesToUsers`. This is the customisation mechanism orgs actually use. Each org can create named permission groups that inherit from a base access level (`parentaccesslevel`) and have individual permission overrides.

## Key Tables

### `kraken_rds.RbacRoles`

| Column | Notes |
|---|---|
| `id` | Primary key |
| `organisationid` | Org this role belongs to |
| `name` | Display name, chosen by the org |
| `parentaccesslevel` | Base system level: `manager`, `supervisor`, `owner`, `employee` |
| `isdefault` | `TRUE` = system-provisioned default template for this org; `FALSE` = org-created custom group |
| `targetgroup` | Scope, such as which staff this applies to |
| `groupids` | Array of section/group IDs this role is scoped to |

- `isdefault=TRUE` rows are auto-created system templates per org, for example "Default Manager Staff View" or "Prevent Supervisor From Sales Data Input". Most orgs have these.
- `isdefault=FALSE` rows are org-created custom permission groups. These are the "custom access levels" users ask about.

### `kraken_rds.RbacRolesToUsers`

| Column | Notes |
|---|---|
| `id` | Primary key |
| `rbacroleid` | FK to `RbacRoles.id` |
| `userid` | User assigned to this role |
| `organisationid` | Org context |

## Production Numbers (as of May 2026)

| Metric | Count |
|---|---:|
| Total `RbacRoles` rows | 18,019 |
| Total `RbacRolesToUsers` rows | 30,292 |
| Custom groups (`isdefault=FALSE`) | ~3,788 |
| Orgs with custom groups (non-test) | 240 |
| Users assigned to custom groups (non-test) | 2,423 |
| Custom groups total across those orgs | 493 |
| Users on default RBAC templates (`isdefault=TRUE`) | ~15,942 |

## `isaccesslevelrenamed` Flag

- Stored in `OrganisationDetails.flags.isaccesslevelrenamed` as a boolean.
- In `OrganisationDetails`: only `false` or `null`, never `true` in production.
- Conclusion: the label-rename feature was built but never activated for any org. Orgs achieve the same outcome via custom RBAC permission groups.

## Common Custom Group Name Patterns

Orgs overwhelmingly customise the `manager` parent access level, roughly 90% of custom groups.

Common naming patterns:

- Job title alignment: "Assistant Manager", "Area Manager", "Store Manager", "2IC", "Outlet PIC", "Cluster Heads", "HQ Department Manager".
- Timesheet restriction: "Manager Cannot Edit Timesheet (All)", "Manager Block Edit Own Timesheet", "Manager Edit Timesheet Employee Only".
- Permission scoping: "Manager Schedule Only", "Manager - Deny add staff", "Owners - No Leave Setting/Editing Access", "Owner Without Payroll Access".
- Descriptive: "Default Manager Staff View", "RAM" (RPG Commerce), "BLOCK ANNOUNCEMENT" (SEONGGONG).

## Org Filter Pitfall

`dim_organisations` is a materialized table that can be empty or stale in BigQuery. When filtering to non-test orgs, use `kraken_rds.OrganisationInformation` directly:

```sql
WITH non_test_orgs AS (
  SELECT DISTINCT id AS org_id, name AS org_name
  FROM `staffany-warehouse`.`kraken_rds`.`OrganisationInformation`
  WHERE LOWER(name) NOT LIKE '%test%'
    AND LOWER(name) NOT LIKE '%demo%'
    AND LOWER(name) NOT LIKE '%staffany%'
    AND LOWER(name) NOT LIKE '%dummy%'
    AND LOWER(name) NOT LIKE '%internal%'
)
```

Then join `RbacRoles.organisationid` to `non_test_orgs.org_id`.
