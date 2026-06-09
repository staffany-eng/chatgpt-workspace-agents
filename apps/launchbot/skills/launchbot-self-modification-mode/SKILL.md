# Launchbot Self Modification Mode

Use this mode only when a teammate explicitly asks Launchbot to modify itself and the requester is authorized for operational mutations.

## Purpose

This mode lets Launchbot:

- edit its own live prompt, workflow docs, runtime scripts, manifest, and bundled skills
- add or adjust bundled skills under the Launchbot app packet
- keep changes scoped to Launchbot's own profile and app packet
- persist those changes back into the source-of-truth repo and redeploy them on request

## Entry

Enter only when all conditions are true:

- the Slack message explicitly mentions `@Launch Bot`
- the user explicitly asks to `enter self modification mode` or clearly asks Launchbot to modify its own workflow / skills / runtime
- the requester is allowed by `LAUNCHBOT_RUNTIME_UPDATE_APPROVER_USER_IDS` when that allowlist is configured

## While In Mode

- Prefer editing under `~/.hermes/profiles/launchbot/source/launchbot/` or `~/.hermes/profiles/launchbot/skills/`.
- Keep changes inside Launchbot scope. Do not mutate unrelated repos, system services, or global Hermes code unless the task genuinely requires it for Launchbot to work.
- Before substantial edits, summarize the intended target files and outcome briefly in Slack.
- Treat workflow, prompt, manifest, runtime docs, and skills as durable artifacts, not one-off conversation text.
- If a requested change would weaken Launchbot's safety boundaries, say so explicitly and keep the operational allowlist gate intact.

## Persist And Deploy

When the user asks to persist, deploy, push, or restart the self-modification changes:

- Use `/home/leekaiyi/.hermes/profiles/launchbot/scripts/launchbot-sync-app-to-repo.sh`.
- Add `--commit` when the user wants a repo commit.
- Add `--push` when the user wants the repo pushed to `origin/main`.
- Pass the requester Slack user ID as `LAUNCHBOT_REQUESTER_SLACK_USER_ID`.

Expected immediate outcomes:

- `launchbot-app-sync:no-change:<sha>`
- `launchbot-app-sync:scheduled:<sha>:<unit>`
- `launchbot-app-sync:error:<reason>`

## Exit

Exit when:

- the user explicitly says to exit self modification mode
- deployment is scheduled or completed
- the task is finished and Launchbot has returned to normal product workflow handling
