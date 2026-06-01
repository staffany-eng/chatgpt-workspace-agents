# References

## Jira

- `SCHE-19906`: Product story for muting PS WEE / PSM Ops Bot over-participation in Slack threads. Derived the core requirement that public-channel participation must be strict mention opt-in across all thread turns.

## Obsidian

- `PS Wee Manager Bot/03 P0 - Stop the Bleeding.md`, P0.3: Local product notes for stopping PS Wee Manager Bot over-participation. Derived the P0 behavior that the bot should stay silent on untagged follow-ups and only resume after a fresh direct mention.

## Slack Feedback

- `https://staffany.slack.com/archives/C08SDJR03N1/p1780113986479539`: Feedback thread reporting Hermes/PS WEE over-participation. Derived the need to treat same-thread replies as not addressed to the bot unless the current Slack message directly mentions it.

## Source Thread Evidence

- Beatrice Clothing Slack source thread: Example where PS WEE replied to untagged follow-up discussion after the first tagged ticket request. Derived the regression case that prior mention, prior bot reply, or active thread session must not authorize later reactive replies.

## Hermes Runtime Docs

- `research/wiki/sources/hermes-agent-docs.md` and `research/wiki/syntheses/hermes-runtime-bot-operating-model.md`: Runtime behavior notes for `slack.require_mention` and `slack.strict_mention`. Derived the implementation approach of enabling `slack.strict_mention: true` instead of relying only on `slack.require_mention: true`.
