# Spec: PSM Ops Slack Participation

## ADDED Requirements

### Requirement: Strict Mention Opt-In

The PSM Ops Bot SHALL answer reactive public/open-channel Slack messages only when the current message directly mentions PS WEE / the bot.

#### Scenario: Untagged same-thread reply after bot response

- GIVEN a user directly mentions PS WEE in a Slack thread
- AND the bot replies
- WHEN a later human reply in the same thread does not directly mention PS WEE / the bot
- THEN the gateway SHALL NOT start an agent turn for that message
- AND the bot SHALL NOT post a Slack reply
- AND the bot SHALL NOT sync that untagged context to Jira.

#### Scenario: Prior thread mention exists

- GIVEN the bot was previously mentioned in a Slack thread
- WHEN a later message in that thread does not directly mention PS WEE / the bot
- THEN the prior mention SHALL NOT count as permission to answer.

#### Scenario: Quieting signal

- GIVEN a Slack thread contains "stay quiet", "stop commenting", "do not reply", or equivalent
- WHEN later messages do not directly mention PS WEE / the bot
- THEN the bot SHALL remain silent until a later direct mention.

#### Scenario: Bot-owned automation is not reactive participation

- GIVEN a PSM Ops cron, central audit copy, or AA push flow starts from bot-owned automation
- WHEN it posts with the required automation identity
- THEN strict mention opt-in SHALL NOT block that bot-owned automation start.
