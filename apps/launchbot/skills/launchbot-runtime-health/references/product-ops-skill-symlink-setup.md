# Product Ops Skill Symlink Setup

**Context:** As of 2026-05-28, the `product-ops-bot-full-workflow` skill bundle was added to the repo
(`apps/launchbot/skills/product-ops-bot-full-workflow/`) but its nested skills were not auto-symlinked
into the live profile on `git pull`. This caused `skill_view('product-ops-intake-linking')` to fail with
"skill not found" even though the skill existed on disk — breaking SOUL.md's routing to the product-ops lane.

## One-Time Setup (run after first pull or on any new VM)

```bash
REPO=/home/leekaiyi/chatgpt-workspace-agents/apps/launchbot/skills/product-ops-bot-full-workflow
PROFILE=/home/leekaiyi/.hermes/profiles/launchbot/skills

# Top-level bundle
ln -s $REPO $PROFILE/product-ops-bot-full-workflow

# Nested skills → devops category
ln -s $REPO/workflow/skills/product-ops-intake-linking        $PROFILE/devops/product-ops-intake-linking
ln -s $REPO/workflow/skills/staffany-product-delivery-workflow $PROFILE/devops/staffany-product-delivery-workflow
ln -s $REPO/workflow/skills/product-ops-bot                   $PROFILE/devops/product-ops-bot
```

## Verification

```bash
ls -la /home/leekaiyi/.hermes/profiles/launchbot/skills/devops/ | grep product-ops
ls -la /home/leekaiyi/.hermes/profiles/launchbot/skills/ | grep product-ops-bot-full-workflow
```

Both should show `lrwxrwxrwx` entries pointing into the repo.

Then confirm the skill is indexed:

```
skill_view(name='product-ops-intake-linking')
```

If it returns content, the symlinks are live and the skill index has refreshed (happens on next gateway restart).

## Why This Is Manual

`git pull` on `chatgpt-workspace-agents` pulls the files but does not create symlinks.
The symlink architecture was established 2026-05-28 to make `git pull` the only sync step needed —
but only for skills that were symlinked at migration time. New skill directories added to
`apps/launchbot/skills/` after that date need a one-time `ln -s` command before they become
accessible in the profile.
