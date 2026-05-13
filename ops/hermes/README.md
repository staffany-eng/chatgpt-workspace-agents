# Hermes Reliability Ops

This directory is the repo-owned control plane for StaffAny Hermes profiles.

## Source Of Truth

- `profiles.yaml` is the profile registry: profile name, source packet, service label, Slack channels, MCP expectations, crons, and recovery policy.
- `channels.md` is the quick channel map for live Slack smoke tests.
- `caretaker.mjs` is a no-agent watchdog. It can run dry-run diagnostics or apply bounded repairs.
- `run-caretaker.sh` and `launchd/ai.hermes.caretaker.plist` install the machine-local 5-minute LaunchAgent runner.
- `test/` contains pure unit tests for repair decisions and registry parsing.

Live profile state under `~/.hermes/profiles/*` is runtime state. Durable behavior belongs in `apps/<app>/` packets and this ops registry.

## Safe Usage

Dry-run all profiles:

```bash
node ops/hermes/caretaker.mjs --dry-run
```

Dry-run one profile:

```bash
node ops/hermes/caretaker.mjs --dry-run --profile nurtureanysalesbot
```

Apply bounded repairs:

```bash
node ops/hermes/caretaker.mjs --apply --profile nurtureanysalesbot
```

Install or refresh the macOS 5-minute runner:

```bash
chmod +x ops/hermes/run-caretaker.sh
mkdir -p ~/.hermes/logs ~/Library/LaunchAgents
install -m 644 ops/hermes/launchd/ai.hermes.caretaker.plist ~/Library/LaunchAgents/ai.hermes.caretaker.plist
launchctl bootout gui/$(id -u)/ai.hermes.caretaker >/dev/null 2>&1 || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.caretaker.plist
launchctl enable gui/$(id -u)/ai.hermes.caretaker
launchctl kickstart -k gui/$(id -u)/ai.hermes.caretaker
```

The caretaker never uses Kai Yi's Slack user token. Slack inspection and optional repair reports use the profile's own bot token from the deployed profile `.env`.

## Repair Boundaries

Allowed automatic repairs:

- create a canonical profile alias when the registry explicitly allows it;
- enable, start, refresh, or restart a managed gateway service when launchd is disabled, the service definition is stale, the service is down, or Slack socket is stale;
- pause active unsafe crons, including legacy NurtureAny event ROI jobs;
- write a redacted operation-ledger event;
- post a bot-owned repair report with the configured automation prefix.

Manual-review repairs:

- secret creation or rotation;
- Slack channel invites/membership changes;
- external message sends;
- HubSpot writes;
- profile sync if the source packet and live profile differ in a way the audit cannot classify.

NurtureAny workflow continuation is handled by its existing `record_nurtureany_operation_checkpoint` and `read_nurtureany_operation_ledger` MCP tools. The caretaker can report stuck/interrupted threads, but it must not repeat writes or sends.
