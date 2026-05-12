# Launch Superpower Bot Regression Cases

## Help Article Drafting

- Given `KER-1742` / ClubAny brand and perk management, Step 1 should prefer one combined management article with `Managing Brands`, `Managing Perks`, and `FAQ`.
- Draft markdown must not include raw HTML tags, text divider lines, repeated title text in the body, or internal appendix content.
- Audience block must include Tier, Product, Platform, and Access Level; ClubAny / Club Blue content must use `Product: StaffAny`.
- The guide outline must be a numbered list, and numbered steps must restart at `1` for each subsection.
- Internal notes must include source of truth, repo and branch or sha, key paths or symbols, API/data touchpoints, assumptions, and last verified commit outside the publishable body.

## Google Docs Promotion

- A single-article legacy manifest should be upgraded into a structured article record without losing article slug, title, markdown, or internal notes.
- Multiple articles should create and track separate Google Docs and Slack review messages.
- Slack review messages must be posted by the bot identity when posting is enabled.

## Slack Approval To Intercom Draft

- A configured approval reaction from an authorized reviewer should create one Intercom draft for the matching article slug.
- Unauthorized reviewer reactions should be ignored.
- The bot should post a progress reply before draft creation and a final reply with the draft link or draft ID after creation.
- Successful Intercom draft responses without a returned URL should still be accepted when an article ID is present.

## Intercom HTML Normalization

- Google Docs export should remove duplicate title headings and internal appendices.
- Center alignment for the audience block should be preserved.
- Google Docs bold spans should become semantic strong text where possible.
- Body-level `h1` headings should be converted below the article title level.
- Stable heading anchors should be present for section links where possible.

## Known Gap Guards

- Do not report Step 4 launch derivatives as implemented.
- Do not claim screenshot capture is automated until source code exists and is tested.
- Do not claim visual DOCX QA is complete unless a renderer was actually run.
