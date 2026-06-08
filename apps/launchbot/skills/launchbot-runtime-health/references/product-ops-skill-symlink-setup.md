# Product Ops Skill Runtime Setup

> Historical note: this file originally documented the May 2026 symlink setup. Current Launchbot runtime repair must not create symlinks for skills. Use the materialized sync workflow below.

**Context:** As of 2026-05-28, the `product-ops-bot-full-workflow` skill bundle was added to the repo
(`apps/launchbot/skills/product-ops-bot-full-workflow/`) but its nested skills were not auto-symlinked
into the live profile on `git pull`. This caused `skill_view('product-ops-intake-linking')` to fail with
"skill not found" even though the skill existed on disk — breaking SOUL.md's routing to the product-ops lane.

## One-Time Setup (run after first pull or on any new VM)

```bash
cd /home/leekaiyi/chatgpt-workspace-agents
bash apps/launchbot/runtime/sync-live-profile.sh
```

## Verification

```bash
ls -la /home/leekaiyi/.hermes/profiles/launchbot/skills/devops/ | grep product-ops
ls -la /home/leekaiyi/.hermes/profiles/launchbot/skills/ | grep product-ops-bot-full-workflow
```

The top-level `product-ops-bot-full-workflow` directory should exist as a real directory copied from the repo.

Then confirm the skill is indexed:

```
skill_view(name='product-ops-intake-linking')
```

If it returns content, the copied skill is live and the skill index has refreshed (happens on next gateway restart).

## Why This Is Manual

`git pull` on `chatgpt-workspace-agents` pulls the files but does not copy them into the live profile.
New skill directories added under `apps/launchbot/skills/` must be added to the Launchbot sync/deploy allowlists,
then copied with `apps/launchbot/runtime/sync-live-profile.sh` before they become accessible in the profile.
