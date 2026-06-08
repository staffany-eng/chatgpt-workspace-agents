---
name: launchbot-runtime-health
description: >
  Audit Launchbot runtime health on the VM: gateway start times, deploy version,
  who deployed, and process topology. Use when a teammate asks about the latest
  deployment, uptime, or whether Launchbot is live.
triggers:
  - "when's your latest deployment"
  - "who deployed"
  - "is launchbot running"
  - "launchbot health"
  - "gateway status"
  - "last deploy"
  - "do you have the workflow of"
  - "what does X bot do"
  - "is there overlap between"
  - "set up auto-deploy"
  - "auto sync"
  - "sync from repo"
  - "changes not reflected"
  - "switch to kaiyisg/main"
  - "track origin/main"
  - "always use latest branch"
  - "make running binary use"
  - "push local changes"
  - "pull latest repo"
  - "update yourself"
  - "sync latest launchbot repo"
  - "restart if there are updates"
tags: [launchbot, runtime, devops, health, deployment]
---

# Launchbot Runtime Health

## Key Facts (VM-primary topology)

Launchbot runs **directly on the VM** as a Hermes gateway process under the `leekaiyi` user.
It is **NOT** deployed as a GCP Cloud Run service — `gcloud run revisions list` returns empty.
GCP project is `staffany-warehouse`.

## Other Bots on the Same VM

Four Hermes profiles are live under `/home/leekaiyi/.hermes/profiles/`:

| Profile dir | App source packet | Bot name |
|---|---|---|
| `launchbot` | `apps/launchbot/` | Launchbot |
| `productopsbot` | `apps/product-ops-bot/` | Product Ops Bot |
| `nurtureanysalesbot` | `apps/nurtureany-sales-bot/` (assumed) | NurtureAny Sales Bot |
| `staffanydatabot` | `apps/staffany-data-bot/` (assumed) | StaffAny Data Bot |

Source packet canonical path: `/home/leekaiyi/chatgpt-workspace-agents/apps/<bot-slug>/`

When a teammate asks "do you have the workflow for X bot", check:
1. `apps/<bot-slug>/profile/SOUL.md` — core role + output contract
2. `apps/<bot-slug>/runtime/slack.md` — Slack routing + skill dispatch rules
3. `apps/<bot-slug>/skills/` — skill names and trigger routing
4. `apps/<bot-slug>/runtime/health-checks.md` — health check commands

Profile path: `/home/leekaiyi/.hermes/profiles/launchbot/`
Logs path: `/home/leekaiyi/.hermes/profiles/launchbot/logs/`

## Step-by-Step: Audit Deploy/Runtime State

### 1. When did the gateway last start?

```bash
grep "Starting Hermes Gateway" /home/leekaiyi/.hermes/profiles/launchbot/logs/gateway.log | tail -5
```

Returns timestamped lines for each restart. Most recent = last gateway start.

### 2. What version is running?

```bash
cat /home/leekaiyi/.hermes/profiles/launchbot/VERSION
```

Returns a git commit hash. **This is a manually-pinned file — it can be stale and does NOT control what code runs.** The gateway service runs directly from the checkout at `/home/leekaiyi/.hermes/hermes-agent/`; the actual running code is always whatever `git rev-parse HEAD` says in that checkout.

To sync `VERSION` to the current HEAD:
```bash
cd /home/leekaiyi/.hermes/hermes-agent && git rev-parse HEAD > /home/leekaiyi/.hermes/profiles/launchbot/VERSION
```

### 3. What's the latest hermes-agent commit?

```bash
cd /home/leekaiyi/.hermes/hermes-agent && git log --oneline -5
```

Shows local HEAD. The service runs directly from this checkout — local HEAD = what's running.

**Remote topology (three remotes):**
- `kaiyisg` → `https://github.com/kaiyisg/hermes-agent.git` — **Kai Yi's StaffAny fork. This is the StaffAny-canonical remote.**
- `all-staffany` → `https://github.com/all-staffany/hermes-agent.git` — StaffAny org remote (fewer branches).
- `origin` → `https://github.com/NousResearch/hermes-agent.git` — upstream NousResearch public repo. **NOT the StaffAny source.**

When checking "is hermes-agent up to date for StaffAny?", always compare against `kaiyisg/main`, not `origin/main`. `origin/main` is far ahead (NousResearch public) and not what Launchbot tracks.

To check latest StaffAny fork commit:
```bash
cd /home/leekaiyi/.hermes/hermes-agent && git log kaiyisg/main --oneline -5
```

**Warning:** `git fetch` on hermes-agent remotes can time out (300s+) inside `execute_code`. Use the `terminal()` tool with explicit `timeout` parameter instead.

### 3b. What's the latest Launchbot app commit (source packet)?

The Launchbot **profile/SOUL.md, skills, and app config** live in a separate repo:

```bash
cd /home/leekaiyi/chatgpt-workspace-agents && git log --oneline -5
git fetch origin && git log origin/main --oneline -5
```

Remote: `https://github.com/staffany-eng/chatgpt-workspace-agents.git`
This repo is the canonical source for Launchbot profile changes (SOUL.md, skills, runtime docs).
The local checkout is often **behind origin/main** — always fetch before reporting the latest commit.

### 3d. Apply the latest Launchbot app commit safely

When the ask is not just "what is the latest commit?" but "pull the latest repo and restart Launchbot if needed", use the profile-local update entrypoint:

```bash
/home/leekaiyi/.hermes/profiles/launchbot/scripts/launchbot-update-app-from-repo.sh
```

Expected outputs:
- `launchbot-app-update:no-change:<sha>` — already current; do not restart
- `launchbot-app-update:scheduled:<from_sha>:<to_sha>:<unit>` — a detached user unit will pull, sync, restart, and health-check Launchbot
- `launchbot-app-update:error:<reason>` — blocked; report the exact reason

Why this exists:
- A direct `systemctl --user restart hermes-gateway-launchbot.service` from inside Launchbot can kill the current Slack request before it replies.
- The update script schedules a detached user unit first, then returns immediately so Launchbot can answer in Slack before the restart begins.

### 3c. Has a specific commit's changes actually been applied to the runtime profile?

When the local repo is stale but changes may have been applied directly to the deployed profile files:

```bash
# Example: verify commit cdca49a (which touched SOUL.md) is live
grep -n "Hard gate" /home/leekaiyi/.hermes/profiles/launchbot/SOUL.md
```

If the grep hits, the change is live regardless of local repo HEAD. This matters because:
- Changes can be patched directly to `/home/leekaiyi/.hermes/profiles/launchbot/` files
  without a `git pull` on the local checkout.
- The local repo and the deployed runtime profile can diverge.

To check what a commit touched:
```bash
cd /home/leekaiyi/chatgpt-workspace-agents && git show <sha> --stat
git show <sha> -- apps/launchbot/profile/SOUL.md
```
Then grep for a distinctive string from the diff in the live profile file.

### 4. Who deployed?

The gateway runs under the `leekaiyi` VM user. There is no separate deploy log with a
named human deployer. To trace who pushed the latest code:
- For hermes-agent runtime: check `git log` in `/home/leekaiyi/.hermes/hermes-agent`.
- For Launchbot app changes: check `git log origin/main` in `/home/leekaiyi/chatgpt-workspace-agents` or the GitHub repo.
- Commit author in `chatgpt-workspace-agents` is the most reliable human attribution.

### 5. Is the gateway process currently alive?

```bash
cat /home/leekaiyi/.hermes/profiles/launchbot/gateway.pid 2>/dev/null
# Then verify:
ps -p <pid> 2>/dev/null
```

Or check `gateway.lock` existence as a proxy.

### 6. Profile directory overview (quick sanity check)

```bash
ls /home/leekaiyi/.hermes/profiles/launchbot/
```

Presence of `gateway.pid`, `gateway.lock`, `gateway_state.json` = gateway has been started.

## Cross-App Filesystem Fallback (Always Apply)

When asked about **any** StaffAny Hermes app — product-ops-bot, nurtureanysalesbot, staffanydatabot, psm-ops-bot, or any future app — do NOT stop at "not in my skills list." The skills list only reflects the *current profile's* skills. All app source packets are readable from the filesystem:

- Source packet: `/home/leekaiyi/chatgpt-workspace-agents/apps/<app-name>/` — skills, `profile/SOUL.md`, `runtime/*.md`
- Live profile: `/home/leekaiyi/.hermes/profiles/<profilename>/`
- For the full app inventory and overlap map, see `references/staffany-app-overlap-map.md`

**Correct fallback sequence when asked about another app:**
1. `ls /home/leekaiyi/chatgpt-workspace-agents/apps/` to confirm the app directory name
2. `ls apps/<app-name>/skills/` to enumerate skills
3. `read_file` on each `SKILL.md` directly
4. Optionally read `profile/SOUL.md` and `runtime/slack.md` for routing rules

Never say "I don't have visibility" when the files are on the same VM.

---

## Pitfalls

- **`VERSION` file is a stale pin, not the running version** — The gateway runs directly from the `/home/leekaiyi/.hermes/hermes-agent/` checkout. `VERSION` is just a file that can drift from actual HEAD. Always check `git rev-parse HEAD` in the checkout for the true running version. If updating the version for a teammate, write: `git rev-parse HEAD > /home/leekaiyi/.hermes/profiles/launchbot/VERSION`.
- **`origin` remote is NousResearch public, NOT StaffAny** — `origin/main` on hermes-agent is the upstream NousResearch repo and is far ahead of what Launchbot uses. Always use `kaiyisg/main` to check the latest StaffAny-relevant hermes-agent commit.
- **`git fetch` on hermes-agent can time out in execute_code** — Use the `terminal()` tool directly with an explicit `timeout` (e.g. 30s) when running git commands against hermes-agent remotes. The `execute_code` wrapper hits a 300s hard ceiling and stalls the session.
- **Do NOT check `gcloud run revisions list`** — Launchbot is not on Cloud Run; the command returns empty and wastes time.
- **`launchbot_product_gap_triage_server.py` was removed from the repo** — As of 2026-05-28, Abel confirmed the product gap triage MCP server should not exist. The files `launchbot_product_gap_triage_server.py` and `test_launchbot_product_gap_triage_server.py` were removed from `apps/launchbot/runtime/mcp/`. Do not recreate them. If you find them in the profile, delete them.
- **Product-ops-bot takes priority for customer triage KER & IFI work** — Abel confirmed 2026-05-28: for customer request triage requiring CRUD on IFI or KER tickets, product-ops-bot should handle it. Launchbot's KER/IFI lane is for launch-asset workflow only (APQ/BD notes, HubSpot-linked). Defer customer triage ticket work to product-ops-bot when it is available.
- **Some Launchbot-specific devops skills may still not be repo-backed** — If a skill exists only in the runtime profile, move it into `apps/launchbot/skills/`, add it to `required_skills` in `runtime/sync-live-profile.sh`, and update the verifier/deploy checks as needed. Until then, edits to that skill are runtime-only and will not survive a profile rebuild.
- **New skills added to `apps/launchbot/skills/` are not automatically exposed** — `git pull` on `chatgpt-workspace-agents` pulls the files but does not copy them into the live profile. After adding a skill directory under `apps/launchbot/skills/`, add it to the sync/deploy allowlists and run the sync:
  ```bash
  cd /home/leekaiyi/chatgpt-workspace-agents
  bash apps/launchbot/runtime/sync-live-profile.sh
  ```
  Confirm with `ls -la /home/leekaiyi/.hermes/profiles/launchbot/skills/` and `skill_view(name)` after syncing. First discovered 2026-05-28 when `product-ops-intake-linking` was missing despite being in the repo.
- **SOUL.md can reference skills that don't exist on disk** — `product-ops-intake-linking` was referenced in SOUL.md as a required routing skill but never created, causing silent routing failures (Launchbot ran the wrong tools before redirecting). When debugging unexpected routing behavior, check: `skills_list()` and cross-reference against every skill name mentioned in SOUL.md. Any mismatch = dangling reference = create the skill or remove the reference. Found and fixed 2026-05-28.
- **`agent-builder/` has been deleted** — As of 2026-05-28, `/home/leekaiyi/agent-builder/` and `/home/leekaiyi/chatgpt-workspace-agents-launchbot-try/` no longer exist on the VM. The canonical app source packet is `/home/leekaiyi/chatgpt-workspace-agents/` (git repo, remote: `staffany-eng/chatgpt-workspace-agents`). Do not reference `agent-builder/` in any path.
- **Local `chatgpt-workspace-agents` is frequently behind origin/main** — always `git fetch origin` before reporting the latest commit. In this session it was 293 commits behind. The local repo being stale does NOT mean the runtime profile is stale — changes may have been applied directly to profile files.
- **Two separate repos, two separate concerns** — `hermes-agent` = the Hermes runtime binary version. `chatgpt-workspace-agents` = Launchbot's SOUL.md, skills, and app config. A deploy question may need both checked.
- **Multiple restarts per day are normal** — The gateway restarts frequently (5+ times in one day is observed). Each restart line in `gateway.log` is not a new deploy; it may be a config reload or crash-recovery.
- **No named human deployer in logs** — The deploy trail only shows the VM user (`leekaiyi`). For human attribution, check GitHub commit history directly.
- **`~` path expansion is broken on this VM** — Always use absolute paths like `/home/leekaiyi/...`. Tilde expands to a double-home path under the Hermes profile CWD.

## Switching hermes-agent to Track a Specific Branch

When Abel (or anyone) asks to make the running binary track a specific branch (e.g. always `kaiyisg/main`):

### Step 1 — Check for local dirty state first

```bash
cd /home/leekaiyi/.hermes/hermes-agent && git status --short && git branch
```

If `gateway/run.py` or any other file is modified (shows `M`), **do not switch branches yet**. Inspect the diff and ask the user whether to discard or preserve it:

```bash
git diff gateway/run.py | head -80
```

### Step 2 — Handle local changes (ask user for option 1 or 2)

**Option 1 — Discard:** `git checkout -- .` then proceed to Step 3.

**Option 2 — Commit + push to target branch first:**
```bash
git add <file> && git commit -m "<message>"
git push kaiyisg <current-branch>:main
```
⚠️ **GitHub push from VM is blocked** — no SSH key, no HTTPS token, no `gh` CLI, no `.netrc`. All pushes from the VM to GitHub fail with `Permission denied (publickey)` or `could not read Username`. Kai Yi must push from their local machine. Stop here and ask Kai Yi to push, then continue once confirmed.

### Step 3 — Switch checkout to target branch

After local changes are resolved:

```bash
cd /home/leekaiyi/.hermes/hermes-agent
git checkout main          # switch to local main
git branch -u kaiyisg/main main  # set upstream to kaiyisg/main
git pull kaiyisg main      # fast-forward to latest
```

### Step 4 — Update VERSION and restart service

```bash
git rev-parse HEAD > /home/leekaiyi/.hermes/profiles/launchbot/VERSION
systemctl --user restart hermes-gateway-launchbot.service
```

### Step 5 — Verify

```bash
grep "Starting Hermes Gateway" /home/leekaiyi/.hermes/profiles/launchbot/logs/gateway.log | tail -3
cat /home/leekaiyi/.hermes/profiles/launchbot/VERSION
```

### Pitfalls for this workflow

- **GitHub push from VM always fails** — there is no GitHub auth on the VM (confirmed 2026-05-25). SSH gives `Permission denied (publickey)`, HTTPS gives `could not read Username`. Only Kai Yi can push from their local machine.
- **`origin/main` is NousResearch, not StaffAny** — never set the branch upstream to `origin/main`. Use `kaiyisg/main`.
- **Check for uncommitted local-only changes before any branch switch** — they can silently represent in-progress features not yet pushed anywhere (e.g. `feat/slack-restart-recovery-notice` had local-only `gateway/run.py` changes).

## GitHub Actions → SSH Deploy (Option 3: Post-push auto-sync)

When Abel asks to set up automatic sync of `chatgpt-workspace-agents` to the VM triggered by GitHub push:

**Approach:** GitHub Actions workflow SSHes into the VM on every push to `main` and runs `git pull`. No public webhook server required on the VM.

**Existing deploy key (as of 2026-05-28):**
- Private key: `/home/leekaiyi/.ssh/id_ed25519_github_deploy`
- Public key: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHfKW10KCksJGNInEpaK7ph2gIOpbIjvHtd1lafDaUln launchbot-vm-deploy@staffany`
- SSH config alias: `github-kaiyisg` in `/home/leekaiyi/.ssh/config`
- ⚠️ Public key is NOT yet in `authorized_keys` — must be added before GitHub Actions can SSH in.

**Setup steps:**
1. Add the existing public key to `authorized_keys` (one-time, run on VM):
   ```bash
   cat /home/leekaiyi/.ssh/id_ed25519_github_deploy.pub >> /home/leekaiyi/.ssh/authorized_keys
   ```
2. Workflow file already written at `chatgpt-workspace-agents/.github/workflows/deploy-pull.yml` (see template below). Commit and push it.
3. Store the **private key** contents as a GitHub Actions secret named `LAUNCHBOT_VM_SSH_KEY` in `staffany-eng/chatgpt-workspace-agents`. Also store `LAUNCHBOT_VM_HOST` (VM external IP from GCP Console) and `LAUNCHBOT_VM_USER` (`leekaiyi`).
   - ⚠️ Never email the private key. Always copy it directly from a VM terminal session or GCP Console SSH.
   - To get VM external IP: GCP Console → Compute Engine → VM instances, or `gcloud compute instances list --project=staffany-warehouse`.

**GitHub Actions workflow template (use `appleboy/ssh-action@v1.0.3`, secret names as shown):**
```yaml
name: Deploy Pull — Sync VM on push to main

on:
  push:
    branches:
      - main

jobs:
  sync-vm:
    name: Pull latest on Launchbot VM
    runs-on: ubuntu-latest

    steps:
      - name: SSH into VM and git pull
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.LAUNCHBOT_VM_HOST }}
          username: ${{ secrets.LAUNCHBOT_VM_USER }}
          key: ${{ secrets.LAUNCHBOT_VM_SSH_KEY }}
          port: 22
          script: |
            set -e
            cd /home/leekaiyi/chatgpt-workspace-agents
            git pull origin main
            echo "✅ Sync complete at $(date)"
```
Secret names: `LAUNCHBOT_VM_HOST`, `LAUNCHBOT_VM_USER`, `LAUNCHBOT_VM_SSH_KEY`.

**What it does NOT do:** The GitHub Actions step only keeps the local git checkout fresh. Runtime artifacts are copied into the live Hermes profile by running `apps/launchbot/runtime/sync-live-profile.sh` on the VM, or by the deploy script. Restart the gateway after syncing when prompt, skill, MCP, or script changes should take effect immediately.

**Pitfall:** GitHub Secrets must be added manually by someone with repo admin access on `staffany-eng/chatgpt-workspace-agents`. Launchbot cannot write GitHub Secrets.

---

## Syncing App Changes from the Repo

> **Current model, as of 2026-06-08:** `chatgpt-workspace-agents/apps/launchbot` is the source of truth, but Hermes runs from `~/.hermes/profiles/launchbot`. Use `runtime/sync-live-profile.sh` to materialize real files/directories into the live profile. Do not symlink Launchbot scripts, skills, or `source/launchbot`; Hermes cron validates resolved script paths and symlinks can make jobs look outside the profile.

**How it works:**
- Script: `/home/leekaiyi/chatgpt-workspace-agents/apps/launchbot/runtime/sync-live-profile.sh`
- Copies `SOUL.md`, runtime scripts, the full app packet under `source/launchbot`, and required skills into the live profile as regular files/directories.
- Removes stale symlink destinations before copying so deploys do not follow a profile symlink back into the source repo.
- Gateway service: `hermes-gateway-launchbot.service` (systemd --user).

**File mapping (repo → live profile):**

| Source (`apps/launchbot/`) | Destination (live profile) |
|---|---|
| `profile/SOUL.md` | `PROFILE_DIR/SOUL.md` |
| `runtime/check-health.sh` | `scripts/launchbot-check-health.sh` |
| `runtime/audit-live-profile.sh` | `scripts/launchbot-audit-live-profile.sh` |
| `runtime/update-pantheon-repo.sh` | `scripts/launchbot-update-pantheon-repo.sh` |
| `runtime/monitor-*.py` | `scripts/launchbot-monitor-*.py` |
| `runtime/mcp/*.py` | `source/launchbot/runtime/mcp/*.py` |
| `runtime/support-watch-whatsapp-refresh.sql` | `source/launchbot/runtime/` |
| `skills/help-article-generator/references/*` | `source/launchbot/skills/help-article-generator/references/` |
| Full `apps/launchbot/` tree | `source/launchbot/` (via rsync) |

**What is NOT synced:** `config.yaml`, `.env`, runtime state, sessions, logs, cron state, and the Pantheon checkout. `config.yaml` contains live secrets and local runtime values; apply config-template changes manually.

**Manual sync workflow:**
```bash
cd /home/leekaiyi/chatgpt-workspace-agents
bash apps/launchbot/runtime/sync-live-profile.sh
systemctl --user restart hermes-gateway-launchbot.service
/home/leekaiyi/.hermes/hermes-agent/venv/bin/hermes -p launchbot cron list
```

If cron still references `/home/leekaiyi/.hermes/profiles/launchbot/scripts/launchbot-sync-app.sh`, remove or disable that old cron entry. That script was part of the older copy-on-cron design and should not be recreated.

## Profile Cleanup Pattern

When Abel says "clean it up" for any profile directory:

1. **Dry-run first** — use `find` to enumerate every target category and print what would be deleted. Show Abel the list before touching anything.
2. **Ask which scope** — if multiple entries exist (e.g. "all 4" vs "keep X"), ask before deleting. Abel answered "all 4" in the 2026-05-28 session.
3. **Use `-exec rm -rf {} +` not glob expansion** — glob-based `rm -rf "$PROFILE/runtime/scripts.bak-"*` can fail silently if no matches. `find ... -exec rm -rf {} +` is safer.
4. **Verify with counts** — after cleanup, run the same `find` commands piped to `wc -l` and confirm all are 0.
5. **Don't clean other profiles without explicit ask** — launchbot cleanup ≠ staffanydatabot cleanup. The 2026-05-28 session found junk in `staffanydatabot` and `nurtureanysalesbot` but did NOT clean them.
6. **Check other profiles after launchbot cleanup** — After cleaning launchbot, show a summary of stray files found in sibling profiles (`staffanydatabot`, `nurtureanysalesbot`) and offer to clean those too. Abel approved cross-profile cleanup in the 2026-05-28 session when shown the list.
7. **`hermes-agent/` source tree can have strays too** — Check `~/.hermes/hermes-agent/gateway/run.py.bak-*` and similar patterns; these are outside the profile dirs but still on the VM.

The canonical dry-run + execute + verify blocks live in `references/profile-directory-structure.md`.

## Materialized Runtime Architecture (as of 2026-06-08)

Abel decided: **`chatgpt-workspace-agents/apps/launchbot/` is the single source of truth.** Hermes still runs from `~/.hermes/profiles/launchbot`, so repo files are materialized into the profile with `apps/launchbot/runtime/sync-live-profile.sh`. `git pull` alone updates the source checkout; run the sync script before expecting runtime behavior to change.

**Materialized paths:**

| Profile path | → Repo path |
|---|---|
| `SOUL.md` | `apps/launchbot/profile/SOUL.md` |
| `skills/<required-skill>/` | `apps/launchbot/skills/<required-skill>/` |
| `scripts/launchbot-check-health.sh` | `apps/launchbot/runtime/check-health.sh` |
| `scripts/launchbot-audit-live-profile.sh` | `apps/launchbot/runtime/audit-live-profile.sh` |
| `scripts/launchbot-monitor-feature-intake.py` | `apps/launchbot/runtime/monitor-feature-intake.py` |
| `scripts/launchbot-monitor-support-watch.py` | `apps/launchbot/runtime/monitor-support-watch.py` |
| `scripts/launchbot-update-pantheon-repo.sh` | `apps/launchbot/runtime/update-pantheon-repo.sh` |
| `runtime/mcp/` | `apps/launchbot/runtime/mcp/` |
| `source/launchbot/` | `apps/launchbot/` |

**What is copied from the repo into the live profile:**
- `SOUL.md`
- Launchbot runtime scripts under `scripts/`
- `source/launchbot/`
- required Launchbot skills under `skills/`

**What is not copied from the repo (intentionally):**
- `config.yaml` — live secrets/env vars differ from template
- `source/pantheon/` — separate git repo
- `runtime/feature-intake-monitor-state.json`, `pantheon-repo-status.json` — live state
- All of `sessions/`, `memories/`, `logs/`, `cron/`, `state.db` — runtime data

**To verify profile path safety:**
```bash
find /home/leekaiyi/.hermes/profiles/launchbot/scripts -maxdepth 1 -type l -ls
find /home/leekaiyi/.hermes/profiles/launchbot/source/launchbot -maxdepth 0 -type l -ls
find /home/leekaiyi/.hermes/profiles/launchbot/skills -maxdepth 1 -type l -ls
```

## Support Files

- `references/product-ops-bot-topology.md` — Product Ops Bot profile location, skill routing, behavioral rules, and health check commands.
- `references/profile-directory-structure.md` — Full inspected map of the live profile dir, what's safe to delete, backup sprawl diagnosis, and the 3-step dry-run→execute→verify cleanup block. Load before answering profile structure or cleanup questions.
- `references/product-ops-skill-symlink-setup.md` — Historical note for the old May 2026 symlink setup. Do not follow its `ln -s` commands for current Launchbot profile repair.

## Answer Shape

When answering a teammate's deploy question, return:

- **Latest gateway start**: timestamp from `gateway.log`
- **Version hash**: from `VERSION` file
- **Latest hermes-agent commit**: from `git log`
- **Latest app commit**: from `git log origin/main` in `chatgpt-workspace-agents` (always fetch first)
- **Who deployed**: VM user `leekaiyi`; for human attribution, point to GitHub commit author
- **Auto-deploy status**: cron job `91a7bd7c0d5d` running `*/5 * * * *`
- **Caveat**: multiple restarts ≠ new deploys; config.yaml changes still require manual apply
