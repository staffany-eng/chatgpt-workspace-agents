# Output Contract

Return the result in this shape unless the caller asks for a different format. For Slack, keep it compact and plain enough to paste directly.

## Account Snapshot

- `Account:` company name
- `Domain:` official domain
- `Persona:` target role, if known
- `Primary angle:` one-line reason this is timely

## Best Signal

- `[Article title](url)` - `YYYY-MM-DD`
- `Type:` funding, leadership, hiring, product, brand-buzz, or news
- `Why it matters:` one or two sentences tied to outreach relevance

## Alternate Signals

List up to 2 additional items in the same compact format.

## Send-Ready Draft

- `Channel:` whatsapp, email, or chat
- `Message:` short ready-to-send copy
- `Delivery:` Manual-review draft only; no external message was sent.

## Sources

List every source used as markdown links.

## NurtureAny Footer

- `Source:` HubSpot scope plus public research/source links
- `Scope:` caller, account/company ID, country, persona/channel, research window, and mode
- `Confidence:` `verified`, `needs-check`, or `blocked`
- `Caveat:` material limitation only

## Example

```md
## Account Snapshot
- Account: Acme Robotics
- Domain: acmerobotics.com
- Persona: HR
- Primary angle: Acme is scaling a new regional team after its warehouse automation rollout.

## Best Signal
- [Acme Robotics launches Southeast Asia warehouse automation program](https://example.com/article) - 2026-05-04
- Type: product
- Why it matters: The launch suggests operational expansion and team growth, which makes a people and enablement conversation timely.

## Alternate Signals
- [Acme opens new operations hub in Johor](https://example.com/article-2) - 2026-04-28
- Type: hiring
- Why it matters: The new hub indicates near-term hiring and onboarding needs.

## Send-Ready Draft
- Channel: whatsapp
- Message: Hi Sarah, I saw Acme Robotics just launched its warehouse automation program in Southeast Asia and thought this coverage might be useful for your team planning: https://example.com/article. Happy to share a couple more relevant ideas if helpful.
- Delivery: Manual-review draft only; no external message was sent.

## Sources
- [Acme Robotics launches Southeast Asia warehouse automation program](https://example.com/article)
- [Acme opens new operations hub in Johor](https://example.com/article-2)

Source: HubSpot scoped account plus public source links above
Scope: selected account; recent public signals; light research mode
Confidence: needs-check
Caveat: Public news is an outreach angle only and does not override HubSpot account truth.
```
