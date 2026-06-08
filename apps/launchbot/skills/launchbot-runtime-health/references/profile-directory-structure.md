# Launchbot Profile Directory Structure
_Inspected and updated 2026-06-08. Use as the canonical map when answering directory or cleanup questions._

## Live directories (keep these)

```
~/.hermes/profiles/launchbot/
├── config.yaml                        # live config — single source of truth (not copied from template)
├── .env                               # live secrets — single source of truth
├── SOUL.md                            # copied from apps/launchbot/profile/SOUL.md
├── VERSION                            # manually-pinned git SHA — can be stale
├── auth.json / auth.lock              # OAuth tokens
├── gateway.lock / gateway.pid / gateway_state.json   # gateway process state
├── channel_directory.json             # Slack channel ID map
├── state.db / state.db-shm / state.db-wal            # Hermes SQLite session store
├── bin/tirith                         # security binary
├── cache/documents, cache/images      # web extraction cache — auto-managed
├── cron/jobs.json + cron/output/      # cron job state + outputs
├── drafts/                            # staging drafts (e.g. help article drafts)
├── home/.cache, home/.config, home/.local, home/.npm  # gcloud/pip/npm cache
├── logs/agent.log, gateway.log, errors.log, mcp-stderr.log  # live logs
├── memories/MEMORY.md                 # persistent agent memory
├── models_dev_cache.json              # model catalog cache
├── plans/                            # implementation plans
├── platforms/pairing/                 # Slack pairing state
├── runtime/
│   ├── feature-intake-monitor-state.json
│   ├── pantheon-repo-status.json
│   └── last-launchbot-deploy-sha
├── sandboxes/singularity/             # container sandbox state
├── scripts/                           # copied runtime scripts; must stay inside profile/scripts
├── sessions/                          # session transcripts (managed by Hermes)
├── skills/
│   ├── help-article-generator/        # copied from apps/launchbot/skills/
│   ├── weekly-support-watch/          # copied from apps/launchbot/skills/
│   └── [other synced skills]
├── source/
│   ├── launchbot/                     # copied app packet from chatgpt-workspace-agents/apps/launchbot/
│   └── pantheon/                      # git checkout of staffany-eng/pantheon (product source of truth)
├── ssh/pantheon_deploy_key            # deploy key for pantheon repo
└── .skills_prompt_snapshot.json       # skills prompt cache
```

## Materialized Runtime Architecture (as of 2026-06-08)

Abel's decision: **`chatgpt-workspace-agents/apps/launchbot/` is the single source of truth.**
Hermes runs from `~/.hermes/profiles/launchbot`, so repo files are copied into the profile with `apps/launchbot/runtime/sync-live-profile.sh`. Do not symlink Launchbot scripts, skills, or `source/launchbot`; Hermes cron validates resolved script paths and symlinked scripts can be blocked.

| Profile path | Repo source |
|---|---|
| `SOUL.md` | `apps/launchbot/profile/SOUL.md` |
| `skills/<required-skill>/` | `apps/launchbot/skills/<required-skill>/` |
| `scripts/launchbot-check-health.sh` | `apps/launchbot/runtime/check-health.sh` |
| `scripts/launchbot-audit-live-profile.sh` | `apps/launchbot/runtime/audit-live-profile.sh` |
| `scripts/launchbot-monitor-feature-intake.py` | `apps/launchbot/runtime/monitor-feature-intake.py` |
| `scripts/launchbot-monitor-support-watch.py` | `apps/launchbot/runtime/monitor-support-watch.py` |
| `scripts/launchbot-update-pantheon-repo.sh` | `apps/launchbot/runtime/update-pantheon-repo.sh` |
| `source/launchbot/` | `apps/launchbot/` |

**Not copied from the repo:** `config.yaml` (live secrets/local config), `.env`, `source/pantheon/` (separate repo), all state/log/session files.

**`launchbot-sync-app.sh` and its cron job are obsolete** — if the cron job still references it, disable/remove that old entry rather than recreating the script.

### Verify path safety

```bash
PROFILE=/home/leekaiyi/.hermes/profiles/launchbot
find "$PROFILE/scripts" -maxdepth 1 -type l -ls
find "$PROFILE/source/launchbot" -maxdepth 0 -type l -ls
find "$PROFILE/skills" -maxdepth 1 -type l -ls
```

### Discrepancy audit (run periodically or before changes)

```bash
REPO=/home/leekaiyi/chatgpt-workspace-agents/apps/launchbot
PROFILE=/home/leekaiyi/.hermes/profiles/launchbot

# 1. SOUL.md — should match repo copy
cmp -s "$REPO/profile/SOUL.md" "$PROFILE/SOUL.md" || echo "SOUL drift"

# 2. MCP: files in live but not in repo
comm -23 <(ls "$PROFILE/runtime/mcp/" | sort) <(ls "$REPO/runtime/mcp/" | sort)

# 3. MCP: files in repo but not in live
comm -13 <(ls "$PROFILE/runtime/mcp/" | sort) <(ls "$REPO/runtime/mcp/" | sort)

# 4. Stray non-symlink files in scripts/
find "$PROFILE/scripts/" -maxdepth 1 -not -type l -not -type d 2>/dev/null

# 5. VERSION match
echo "profile VERSION: $(cat $PROFILE/VERSION)"
echo "repo    VERSION: $(cat $REPO/profile/VERSION 2>/dev/null || echo MISSING)"

# 6. Repo git status
cd "$REPO" && git status --short
```

---

## Cleanup commands (run when Abel says "clean it up")

### Step 1 — dry run first

```bash
PROFILE=/home/leekaiyi/.hermes/profiles/launchbot

echo "=== 1. backups/ subdirs ===" && find "$PROFILE/runtime/backups" -mindepth 1 -maxdepth 1 2>/dev/null || true
echo "=== 2. source/launchbot.backup-* ===" && find "$PROFILE/source" -maxdepth 1 -name "launchbot.backup-*" 2>/dev/null || true
echo "=== 3. runtime/source-launchbot.bak.* ===" && find "$PROFILE/runtime" -maxdepth 1 -name "source-launchbot.bak.*" 2>/dev/null || true
echo "=== 4. runtime/scripts.bak-*, deploy-backups/, backups/ ===" && find "$PROFILE/runtime" -maxdepth 1 -name "scripts.bak-*" 2>/dev/null || true
echo "=== 5. runtime/ root *.bak.* ===" && find "$PROFILE/runtime" -maxdepth 1 -name "*.bak.*" 2>/dev/null || true
echo "=== 6. ._* macOS files ===" && find "$PROFILE" -name "._*" 2>/dev/null || true
echo "=== 7. .env.backup-* and config.yaml.backup-* ===" && find "$PROFILE" -maxdepth 1 \( -name ".env.backup-*" -o -name "config.yaml.backup-*" \) 2>/dev/null || true
```

### Step 2 — execute

```bash
PROFILE=/home/leekaiyi/.hermes/profiles/launchbot

rm -rf "$PROFILE/runtime/backups"
find "$PROFILE/source" -maxdepth 1 -name "launchbot.backup-*" -exec rm -rf {} +
find "$PROFILE/runtime" -maxdepth 1 -name "source-launchbot.bak.*" -exec rm -rf {} +
find "$PROFILE/runtime" -maxdepth 1 -name "scripts.bak-*" -exec rm -rf {} +
rm -rf "$PROFILE/runtime/deploy-backups"
find "$PROFILE/runtime" -maxdepth 1 -name "*.bak.*" -exec rm -f {} +
find "$PROFILE" -name "._*" -exec rm -f {} +
find "$PROFILE" -maxdepth 1 \( -name ".env.backup-*" -o -name "config.yaml.backup-*" \) -exec rm -f {} +
rm -rf "$PROFILE/backups"
echo "Cleanup done."
```

### Step 3 — verify (all counts should be 0)

```bash
PROFILE=/home/leekaiyi/.hermes/profiles/launchbot
echo "runtime/backups entries: $(ls "$PROFILE/runtime/backups" 2>/dev/null | wc -l)"
echo "source/launchbot.backup-*: $(find "$PROFILE/source" -maxdepth 1 -name "launchbot.backup-*" 2>/dev/null | wc -l)"
echo "runtime/source-launchbot.bak.*: $(find "$PROFILE/runtime" -maxdepth 1 -name "source-launchbot.bak.*" 2>/dev/null | wc -l)"
echo "runtime/scripts.bak-*: $(find "$PROFILE/runtime" -maxdepth 1 -name "scripts.bak-*" 2>/dev/null | wc -l)"
echo "runtime/*.bak.*: $(find "$PROFILE/runtime" -maxdepth 1 -name "*.bak.*" 2>/dev/null | wc -l)"
echo "._* files: $(find "$PROFILE" -name "._*" 2>/dev/null | wc -l)"
echo ".env.backup-* / config.yaml.backup-*: $(find "$PROFILE" -maxdepth 1 \( -name ".env.backup-*" -o -name "config.yaml.backup-*" \) 2>/dev/null | wc -l)"
echo "profile/backups/ entries: $(ls "$PROFILE/backups" 2>/dev/null | wc -l)"
```

---

## Backup junk in other profiles (sibling cleanup)

Same pattern exists in sibling profiles. Show Abel after launchbot cleanup and offer to clean:

| Profile | Backup junk | Status |
|---------|-------------|--------|
| `staffanydatabot` | `.env.backup-*` (3), `SOUL.md.backup-*`, `config.yaml.bak-*`, `backups/` dir | Cleaned 2026-05-28 |
| `nurtureanysalesbot` | `backups/` dir | Cleaned 2026-05-28 |
| `~/.hermes/profiles/._staffanydatabot` | macOS `._*` file | Cleaned 2026-05-28 |
| `hermes-agent/gateway/run.py.bak-*` | Stray bak in source checkout | Cleaned 2026-05-28 |

Also check `~/.hermes/hermes-agent/` for stray `.bak-*` files and `~/.hermes/profiles/` root for `._*` macOS files.

## Prevention going forward

- Git is the rollback mechanism for source — don't duplicate full directories as backups
- Only `.env` and `config.yaml` are legitimately worth one backup copy before a change
- `runtime/sync-live-profile.sh` is the normal copy mechanism; avoid ad hoc file copies unless debugging a single drift finding
