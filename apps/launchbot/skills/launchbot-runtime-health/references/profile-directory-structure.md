# Launchbot Profile Directory Structure
_Inspected and updated 2026-05-28. Use as the canonical map when answering directory or cleanup questions._

## Live directories (keep these)

```
~/.hermes/profiles/launchbot/
├── config.yaml                        # live config — single source of truth (NOT symlinked)
├── .env                               # live secrets — single source of truth (NOT symlinked)
├── SOUL.md → chatgpt-workspace-agents/apps/launchbot/profile/SOUL.md   # SYMLINK
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
│   ├── mcp/ → chatgpt-workspace-agents/apps/launchbot/runtime/mcp/    # SYMLINK
│   ├── feature-intake-monitor-state.json
│   ├── pantheon-repo-status.json
│   └── last-launchbot-deploy-sha
├── sandboxes/singularity/             # container sandbox state
├── scripts/                           # symlinks to repo runtime scripts (see table below)
├── sessions/                          # session transcripts (managed by Hermes)
├── skills/
│   ├── help-article-generator/ → chatgpt-workspace-agents/apps/launchbot/skills/help-article-generator/  # SYMLINK
│   ├── weekly-support-watch/ → chatgpt-workspace-agents/apps/launchbot/skills/weekly-support-watch/      # SYMLINK
│   └── [other skills: bundled, not symlinked]
├── source/
│   ├── launchbot/ → chatgpt-workspace-agents/apps/launchbot/          # SYMLINK
│   └── pantheon/                      # git checkout of staffany-eng/pantheon (product source of truth)
├── ssh/pantheon_deploy_key            # deploy key for pantheon repo
└── .skills_prompt_snapshot.json       # skills prompt cache
```

## Symlink Architecture (as of 2026-05-28)

Abel's decision: **`chatgpt-workspace-agents/apps/launchbot/` is the single source of truth.**
`git pull` in that repo is the only step needed to update SOUL.md, skills, scripts, and MCP servers.

| Profile path | → Repo target |
|---|---|
| `SOUL.md` | `apps/launchbot/profile/SOUL.md` |
| `skills/help-article-generator/` | `apps/launchbot/skills/help-article-generator/` |
| `skills/weekly-support-watch/` | `apps/launchbot/skills/weekly-support-watch/` |
| `scripts/launchbot-check-health.sh` | `apps/launchbot/runtime/check-health.sh` |
| `scripts/launchbot-audit-live-profile.sh` | `apps/launchbot/runtime/audit-live-profile.sh` |
| `scripts/launchbot-monitor-feature-intake.py` | `apps/launchbot/runtime/monitor-feature-intake.py` |
| `scripts/launchbot-monitor-support-watch.py` | `apps/launchbot/runtime/monitor-support-watch.py` |
| `scripts/launchbot-update-pantheon-repo.sh` | `apps/launchbot/runtime/update-pantheon-repo.sh` |
| `runtime/mcp/` | `apps/launchbot/runtime/mcp/` |
| `source/launchbot/` | `apps/launchbot/` |

**NOT symlinked:** `config.yaml` (live secrets), `source/pantheon/` (separate repo), all state/log/session files.

**`launchbot-sync-app.sh` and its cron job are OBSOLETE** — removed as part of this migration.

### Verify symlinks are intact

```bash
REPO=/home/leekaiyi/chatgpt-workspace-agents/apps/launchbot
PROFILE=/home/leekaiyi/.hermes/profiles/launchbot
for target in \
  "$PROFILE/SOUL.md" \
  "$PROFILE/skills/help-article-generator" \
  "$PROFILE/skills/weekly-support-watch" \
  "$PROFILE/runtime/mcp" \
  "$PROFILE/source/launchbot"; do
  [ -L "$target" ] && echo "OK  $(readlink $target)" || echo "NOT SYMLINK: $target"
done
```

### Discrepancy audit (run periodically or before changes)

```bash
REPO=/home/leekaiyi/chatgpt-workspace-agents/apps/launchbot
PROFILE=/home/leekaiyi/.hermes/profiles/launchbot

# 1. SOUL.md — should be symlink pointing to repo
ls -la "$PROFILE/SOUL.md"

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
- The symlink architecture eliminates the need for agent-driven file copies entirely
