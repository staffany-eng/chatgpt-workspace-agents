# Model Help Article References

Use these published StaffAny Help Center articles as model references for LaunchBot help article validation.

## Required Model Articles

| Article | URL | Model Use |
| --- | --- | --- |
| Create and Manage Disbursement | https://help.staffany.com/en/articles/13867569-create-and-manage-disbursement | Complex PayrollAny workflow with setup, statuses, eligibility, payment risk, top-up, retry, reports, and high screenshot density. |
| Managing Employee Document Types | https://help.staffany.com/en/articles/14318367-managing-employee-document-types | HRAny setup workflow with concise create/edit/archive/unarchive/use sections and document-type reuse across staff profile and new joiner form. |

## Shared High-Score Patterns

- Title is a direct task phrase, usually present-tense verb-led.
- Subtitle starts with `Learn how to` and states the user goal plainly.
- Audience applicability appears near the top with Product, Platform, and Access Level. Include Tier when the article family uses it.
- Opening copy explains what the feature does, why users need it, and any important availability condition.
- `This guide will cover how to:` appears before the first procedure, and the list mirrors the article sections in order.
- Section headings are action-oriented and map to real user jobs.
- Procedural sections use numbered steps with concrete StaffAny navigation paths and exact UI labels.
- Screenshots are placed immediately after the step or screen they support.
- Statuses, validations, thresholds, irreversible actions, limits, and consequences appear next to the action they affect.
- FAQ or equivalent closing questions cover operational questions users are likely to ask after following the guide.

## Article-Specific Signals

### Create and Manage Disbursement

Use as the model for complex PayrollAny articles.

- Applicability: PayrollAny, Web, Owner.
- Strong structure: create flow, general settings, employee eligibility, bank validation, summary review, top up, manage statuses, retry, history, report download, FAQ.
- Quality signal: financial risks are explicit, including validation, wallet balance, fees, quota, retry, and report details.
- Quality signal: users are told what can and cannot be edited at each state.
- Quality signal: long workflows are decomposed into small sections with screenshots close to the relevant step.

### Managing Employee Document Types

Use as the model for concise HRAny setup and management articles.

- Applicability: HRAny, Web, Owner/Manager.
- Strong structure: create document type, edit existing type, archive/unarchive, use in staff profile, use in new joiner form.
- Quality signal: each management action has a direct path and a clear outcome.
- Quality signal: archive and unarchive behavior is explained as a reversible visibility/control action.
- Quality signal: reuse across related workflows is covered after setup.

## Failure Modes To Penalize

- Guide list does not match section headings.
- Steps use generic language such as `go to the page` or `click the button` instead of exact UI labels.
- Draft invents defaults, thresholds, permissions, statuses, formulas, document behavior, payment behavior, or limits.
- Risks are pushed into a generic notes section instead of appearing near the affected action.
- Screenshots are missing for multi-screen workflows or placed far from the related step.
- Public body includes `Evidence Used`, `Gaps/Assumptions`, TODOs, source paths, Jira/Figma links, or internal URLs.
- Existing article update drops unrelated valid sections, FAQs, screenshots, videos, or caveats.
