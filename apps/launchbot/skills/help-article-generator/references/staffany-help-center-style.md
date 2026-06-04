# StaffAny Help Center Style Reference

Derived from a crawl of the public English StaffAny Help Center sitemap on 2026-05-14.

## Crawl Snapshot

- Source sitemap: `https://help.staffany.com/sitemap.xml`
- English article pages parsed: 267
- Crawl failures: 0
- Articles with screenshots/images: 211
- Articles with tables: 69
- Articles with FAQ-style sections: 90
- Average heading count: about 6 sections per article

## Current Article Shape

Use the newer PayrollAny/HRAny article pattern for new articles:

1. Title
- Prefer action-led titles.
- For new articles, use simple verb + noun wording even though older articles also use gerunds, platform prefixes, and FAQ prefixes.
- Good patterns: `Create Payment`, `Manage Disbursement`, `Top Up Wallet Balance`, `Set Up PPh21 DTP`, `Generate Employee Documents`.

2. Subtitle
- Prefer `Learn how to ...`.
- Keep it one sentence and contextual to the feature.
- Avoid broad product claims in the subtitle; put feature context in the explanation paragraph.

3. Applicability block
- New PayrollAny articles commonly include:
  - `Tier: NA`
  - `Product: PayrollAny`
  - `Platform: Web`
  - `Access Level: Owner`
- Across the crawled corpus, the most common platform is `Web`, the most common access level is `Owner`, and the most common products with explicit product tags are `EngageAny`, `PayrollAny`, `Payroll`, `StaffAny`, `HRAny`, and `HireAny`.
- Use the default PayrollAny block only when the feature request does not provide better values, and continue without pausing only to validate Product, Platform, or Access Level.

4. Quick explanation
- Add a short paragraph before the guide list.
- State what the feature does, when users use it, and any major prerequisite.
- If the feature is gated, beta, country-specific, or sales-enabled, mention that early.

5. Guide list
- For new articles, use `This guide will cover how to:`.
- The older dominant phrase is `This guide will cover the following`, but newer PayrollAny/HRAny articles use `This guide will cover how to`.
- The guide list should mirror article section headers in order.

6. Sections
- Put setup/configuration sections first, then usage/management sections, then reports/downloads/status checks, then FAQ.
- Keep section headers action-led and short.
- Prefer simple present tense verbs:
  - `Create ...`
  - `Set Up ...`
  - `Manage ...`
  - `Review ...`
  - `Download ...`
  - `Submit ...`
  - `Generate ...`
  - `Archive and Unarchive ...`
- Avoid vague headers such as `Overview`, `How It Works`, or `Key Features` unless the article is a concept/reference article rather than a workflow.

7. Step formatting
- Start procedural sections with a task lead-in such as `To create payment:` or `To start disbursement:`.
- Step 1 should tell the user where to go in StaffAny.
- Use concrete paths and UI labels: `Go to Payroll > Payment`, `Click Create Payment`, `Select Business Entity`.
- Keep each step direct and user-facing.
- Place screenshots immediately after the step they support.

8. Conditions and warnings
- Put conditions inside the relevant section, near the affected step.
- Examples of condition placement:
  - Button visibility conditions go beside the click step.
  - Eligibility rules go inside the review section.
  - Setup prerequisites go before the first action that depends on them.
  - Limits and unavailable states go beside the affected action.

9. Tables
- Use tables when explaining statuses, eligibility rules, field definitions, report columns, transfer methods, or calculation components.
- Keep table labels user-facing, not implementation-facing.

10. FAQ
- Add FAQ when users may ask why a button is hidden, why a status appears, why a calculation differs, how multiple runs behave, or what to do after an error.
- Use direct Q/A formatting.
- Put action-oriented troubleshooting answers first, then explanations.

## PayrollAny-Specific Guidance

- Payroll articles often include setup prerequisites before run/use steps.
- Use `PayrollAny` for new PayrollAny-specific articles unless the existing product scope is explicitly `Payroll`.
- Common article flow:
  1. Set up required pay items, employee fields, business entity, or settings.
  2. Create or run payroll/payment/disbursement.
  3. Review generated payroll, payment, payslip, report, or status.
  4. Download/export or publish/finalise when applicable.
  5. Answer calculation/status/visibility questions.
- Use `Adhoc` only when the feature should run separately from standard monthly payroll.
- Mention pay item filtering when timesheet-dependent pay items require a timesheet period.
- For Indonesia payroll, keep tax/category labels exactly as shown in product evidence.

## Evidence Handling

- Existing public articles are style references, not a replacement for code evidence.
- For new article drafts, use current code/product evidence for UI labels, settings, statuses, and conditions.
- Keep `Evidence Used` and `Gaps/Assumptions` outside the public article body.
