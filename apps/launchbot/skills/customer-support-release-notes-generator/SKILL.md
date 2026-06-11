---
name: release-notes-generator
description: Generate concise StaffAny release notes for Sales, PS, CS, and Product from a shipped Jira KER ticket, Launch Priority, verified UI/UX behavior, existing StaffAny feature context, and optional help article link. Use after launch-priority-identifier or when a Jira-to-Slack command asks LaunchBot for release notes.
---

# Release Notes Generator

> **Skill lookup note (confirmed broken — do not retry):** This skill's directory is `customer-support-release-notes-generator/`. Calling `skill_view(name='release-notes-generator')` will ALWAYS fail with "not found" — even though skills_list shows the description under that name. Use the full directory names:
> - Generator: `skill_view(name='customer-support-release-notes-generator')`
> - Validator: `skill_view(name='customer-support-release-notes-validator')`
> - Feedback updater: `skill_view(name='customer-support-release-notes-feedback-updater')`
>
> This was confirmed in KER-1198 session (2026-06-11): three consecutive `skill_view(name='release-notes-generator')` calls all failed before the correct directory name was found via `skills_list` + `ls`.

Generate short release notes for Sales, PS, CS, and Product from a shipped Jira KER ticket.

## Required Inputs

- Jira key and summary.
- Ticket status, preferably `6 - Shipped & Launching` or Done.
- Launch Priority from `launch-priority-identifier`.
- Verified product behavior from Pantheon evidence, screenshots, approved help article draft, or trusted Jira acceptance criteria.
- Help article link, Intercom draft link, or `TBD`.
- Optional screenshot manifest or safe screenshot files from `help-article-screenshot-capture`.

## Drafting Rules

- Be concise. Write for Sales, PS, CS, and Product teammates who need to recognize, explain, and support the change quickly.
- Do not title, label, or describe the output as `CS release notes`, `Customer Support release notes`, or `Customer Service release notes`.
- Include just enough existing StaffAny feature context for the audience to understand where the change fits.
- Focus `What's new` on UI/UX changes from the previous version to the newer one:
  - changed screens, buttons, labels, fields, menus, filters, empty states, errors, flows, permissions, setup surfaces, or user-visible behavior.
  - avoid backend-only details unless they explain a visible support outcome.
- Use plain enablement language, not marketing copy.
- Keep `How this helps users` focused only on end-user, manager, admin, or customer value. Do not explain how the change helps CS, support agents, triage, or internal teams in that section.
- Mention setup only when the customer/admin must configure something, enable a setting, update permissions, migrate data, or use a new help article.
- If no setup is needed, write `None`.
- If the help article is not ready, write `TBD` and include the Intercom draft link if available.
- Keep each section to one short line or 1-2 bullets unless the ticket has multiple user-facing changes.
- Use screenshots sparingly. Approved release-note posts may include only 1-2 screenshots, and each screenshot must directly show the UI/UX change described in `What's new`.
- If screenshots are missing, blocked, sensitive, or not contextually useful, post the release note without screenshots instead of fabricating or padding with generic UI.

## Required Format

Release notes **must** be delivered as Slack Block Kit JSON via `chat.postMessage` blocks. Do not deliver as plain text or mrkdwn-only fallback.

### Block Kit structure (mandatory)

```json
[
  {
    "type": "header",
    "text": {
      "type": "plain_text",
      "text": ":rocket: New Release — <KER-key>: <Ticket Name>",
      "emoji": true
    }
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*Priority:* <P1|P2|P3|P4> — <Priority label>\n*Product Lead:* <Product Lead name>\n*Jira:* <https://staffany.atlassian.net/browse/<KER-key>|<KER-key>>"
    }
  },
  {
    "type": "divider"
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*What's new*\n<1–2 sentences or short bullets on the UI/UX change>"
    }
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*Key capabilities*\n• *<capability>* — <description>\n• ..."
    }
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*How this helps users*\n<1–2 sentences on end-user/admin/manager value>"
    }
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*Setup needed*\n<None | concise setup steps>"
    }
  },
  {
    "type": "section",
    "text": {
      "type": "mrkdwn",
      "text": "*Help article*\n• EN: <https://help.staffany.com/en/articles/<id>-<slug>|<Article Title>>\n• ID: <https://help.staffany.com/id/articles/<id>-<slug>|<Judul Artikel>>"
    }
  }
]
```

**Rules:**
- `header` block text: `🚀 New Release — <KER-key>: <Ticket Name>` — always include KER key AND ticket name.
- Metadata `section`: bold `*Priority:*`, `*Product Lead:*`, `*Jira:*` on separate lines using `\n`.
- `Key capabilities` section: omit if the feature has no distinct sub-capabilities worth enumerating. Include only when there are 2+ discrete user-visible capabilities.
- `Setup needed`: write `None` if no admin/user setup is required.
- `Help article`: use `https://help.staffany.com/...` (NOT `https://app.intercom.com/...` — Intercom draft links are for internal review only; use the live help.staffany.com URL for distribution). If not yet published, link the Intercom draft with `(draft — pending publish)` label.
- `text` fallback at top-level `chat.postMessage` call: set to the header text (e.g. `"Launchbot automation: 🚀 New Release — KER-NNN: Ticket Name"`).

### Priority label mapping

| Priority | Label |
|----------|-------|
| P1 | Critical Fix / Urgent Customer Impact |
| P2 | New Feature / Significant Upgrade to Core Flow |
| P3 | Minor Enhancement / Internal Efficiency |
| P4 | Cosmetic / Copy / Low Visibility |

## Quality Gate

Before returning, check:

- The ticket is shipped or clearly labeled draft preview.
- UI/UX deltas are verified or explicitly marked `needs-check`.
- No internal app names, source paths, implementation-only details, private URLs, PII, or customer-specific names appear.
- The note is useful for CS triage: what changed, what customers see, what setup is needed, where to send them.
- The note is useful for Sales, PS, CS, and Product: product context, visible change, customer value, setup, and help link.
- `How this helps users` contains no CS/support-agent/internal-team explanation.

## Required Validation Checkpoint

After drafting, immediately run `release-notes-validator` with:

```text
jira_key: <KER-key>
jira_status: <status>
launch_priority: <Launch Priority>
source_evidence: <Jira/Pantheon/help article/source summary>
draft: <release note>
help_article_link: <URL | Intercom draft URL | TBD>
```

If the validator returns `revise`, run `release-notes-feedback-updater`, then validate again. If the validator returns `blocked`, stop and name the missing evidence instead of revising from inference.

## Slack Delivery Rules

> See `references/slack-delivery-constraints.md` for confirmed token scope limits, `send_message` MEDIA behavior, and HTML file rendering facts as of 2026-06-11.


### HTML preview delivery in Slack

**Do NOT embed screenshots as base64 in the HTML file for Slack delivery.** A self-contained base64 HTML file renders as a large binary blob — Slack users cannot open it inline and it shows as a non-viewable attachment. Confirmed user complaint: "I cannot view the html."

Correct pattern for Slack release-note delivery:
1. Write a **lightweight HTML file** (no base64 images, ~5KB) with only text, CSS, and placeholder `<img src="...">` pointing to CDN URLs if available.
2. Send the HTML file via `MEDIA:` as a separate attachment.
3. Send screenshots as **separate `MEDIA:` attachments** — do not embed them in the HTML.
4. If `send_message` MEDIA: is used, note that Slack does not support native media delivery via `send_message` — it will be omitted with a warning. Use `files.upload` API separately for image attachments.

### Slack `files.upload` scope requirement

The Launchbot bot token requires `files:write` scope to upload image files to Slack channels. As of the current token, this scope is **missing** — `files.getUploadURLExternal` returns `missing_scope`. Until scope is added, screenshots must be attached manually by the Product Lead from the files posted in the review thread.

When `files.upload` fails with `missing_scope`, include a note in the thread instructing the teammate to manually upload the screenshot files, and attach them in the current thread for easy access.

### Release-note screenshot sensitivity check

Before using any screenshot from the Intercom article CDN in release notes:
1. Download the image to `/tmp/`.
2. Run `vision_analyze` asking: "Is this clean and non-sensitive for release notes? Describe what's shown."
3. If sensitive background elements exist (face photos, real employee names, pay formulas, bank details, private org names), **crop the image** using PIL to isolate only the relevant UI element.
4. Re-check the cropped image with `vision_analyze` before using.
5. Scale images down for Slack: web screenshots → ~560px wide; mobile screenshots → ~320px wide.

```python
from PIL import Image
img = Image.open('/tmp/screenshot.png')
w, h = img.size
# Crop to modal/feature area only (adjust percentages per screenshot)
cropped = img.crop((int(w*0.30), int(h*0.04), int(w*0.68), int(h*0.78)))
scale = 560 / cropped.width
cropped = cropped.resize((560, int(cropped.height * scale)), Image.LANCZOS)
cropped.save('/tmp/screenshot_clean.png', optimize=True)
```

## Screenshot Step

After the release note passes validation and before Product Lead review:

1. Use `help-article-screenshot-capture` to build a tiny release-note shot list, or reuse existing Intercom CDN screenshots from the help article when they exist.
2. Select only screenshots that make the UI/UX delta easier to understand.
3. Capture or attach at most 2 screenshots; prefer 1 when one screenshot explains the change.
4. Reject screenshots that show private customer data, salaries, bank details, employee identifiers, production org names, or unredacted sensitive fields.
5. If capture is blocked, include `Screenshots: none - <blocked reason>` in the review handoff and continue without screenshots.

Screenshot selection rule:

```text
Screenshot 1: the changed screen or entry point users will notice first.
Screenshot 2: only if needed, the before/after result, setup surface, permission surface, or confirmation state.
```

### Pitfall: Intercom article screenshots may contain sensitive background data

Web UI screenshots often show a modal overlaid on a full app window. The background can expose:
- Real or realistic-looking employee names in sidebars
- Face photo thumbnails (biometric data)
- Pay formulas or salary figures in adjacent panels
- Client-specific location or org names

**Mandatory check before using any screenshot from the help article in release notes:**
1. Use `vision_analyze` on each candidate screenshot and ask: "Is this clean/non-sensitive for release notes?"
2. If the background contains sensitive elements, crop to the modal/feature area only using PIL before attaching.
3. Scale web screenshots to ≤600px wide and mobile to ≤320px wide for clean Slack display.

```python
from PIL import Image

# Crop web modal — adjust crop percentages to frame the modal
img = Image.open('/tmp/screenshot_web.png')
w, h = img.size
cropped = img.crop((int(w*0.30), int(h*0.04), int(w*0.68), int(h*0.78)))
cropped = cropped.resize((560, int(cropped.height * 560/cropped.width)), Image.LANCZOS)
cropped.save('/tmp/screenshot_web_clean.png', optimize=True)

# Scale mobile
img2 = Image.open('/tmp/screenshot_mobile.png')
scale = 320 / img2.width
img2 = img2.resize((320, int(img2.height * scale)), Image.LANCZOS)
img2.save('/tmp/screenshot_mobile_clean.png', optimize=True)
```

## Product Lead Review Handoff

After validation returns `pass`, ask the Product Lead for review in Slack:

```text
Launchbot automation: <@product_lead_slack_user_id> please review these release notes for <KER-key>.
Reply in this thread with `@Launch Bot <feedback>` for edits, or `@Launch Bot approve release notes <KER-key>` to send it to #all-product-new-updates.
```

Include the selected screenshot file links or Slack file attachments in the review thread when available.

Do not post to `#all-product-new-updates` until Product Lead approval is explicit.

## HTML Preview Delivery — Pitfall: Do NOT embed base64 images

When delivering a release notes HTML preview in Slack, **never embed screenshots as base64 data URIs** in the HTML file. A base64-embedded HTML file will be ~900KB+ and **cannot be opened or previewed in Slack**. Users will see a blank or unloadable file.

**Correct delivery pattern (confirmed working):**
1. Write a lightweight HTML file (text + CSS only, no embedded images) — keep under 10KB.
2. Save clean screenshot files separately as `.png`.
3. Send all files as **separate `MEDIA:/path/to/file` attachments** in the same Slack reply: HTML first, then screenshot(s).
4. User opens the HTML in their browser; screenshots are viewable inline in Slack.

```
MEDIA:/tmp/ker-XXXX-release-notes.html
MEDIA:/tmp/ker-XXXX_web_clean.png
MEDIA:/tmp/ker-XXXX_mobile_clean.png
```

Never use `<img src="data:image/png;base64,...">` in release notes HTML output. Use plain `<img src="filename.png">` or omit images from the HTML entirely and let the Slack image previews carry the visual.

## Output Contract

```text
Jira: <KER-key>
Launch Priority: <P1 | P2 | P3 | P4 | blank>
Confidence: <verified | needs-check | blocked>

Release Notes (human-readable summary):
- What's new: ...
- Key capabilities: ...
- How this helps users: ...
- Setup needed: ...
- Help article: ...

Slack Blocks (Block Kit JSON for chat.postMessage):
[
  { "type": "header", "text": { "type": "plain_text", "text": ":rocket: New Release — <KER-key>: <Ticket Name>", "emoji": true } },
  { "type": "section", "text": { "type": "mrkdwn", "text": "*Priority:* <P> — <label>\n*Product Lead:* <name>\n*Jira:* <https://staffany.atlassian.net/browse/<KER-key>|<KER-key>>" } },
  { "type": "divider" },
  { "type": "section", "text": { "type": "mrkdwn", "text": "*What's new*\n..." } },
  { "type": "section", "text": { "type": "mrkdwn", "text": "*Key capabilities*\n• *...* — ..." } },
  { "type": "section", "text": { "type": "mrkdwn", "text": "*How this helps users*\n..." } },
  { "type": "section", "text": { "type": "mrkdwn", "text": "*Setup needed*\nNone" } },
  { "type": "section", "text": { "type": "mrkdwn", "text": "*Help article*\n• EN: <URL|Title>\n• ID: <URL|Judul>" } }
]

Evidence Checked:
- <Jira/Pantheon/help article/source summary>

Needs Check:
- <none or exact missing evidence>

Validator:
Decision: <pass | revise | blocked>
Confidence Score: <0-100>
Top reasons: <short bullets>
Required changes: <short bullets or none>

Slack Review:
Product Lead: <@user_id | blocked_missing_mapping>
Approval instruction: @Launch Bot approve release notes <KER-key>
Approved destination: #all-product-new-updates
Screenshots: <none | 1-2 contextually correct screenshots>
```

## Blockers

Return `blocked` instead of release notes when:

- The ticket is not shipped and the user did not ask for a preview.
- There is no verified customer-visible behavior.
- The only known change is sensitive, negative, or operationally risky to broadcast.
- The draft would require inventing UI labels, setup steps, availability, or help article links.
