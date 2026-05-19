---
name: gryphon-storybook-prototype-handoff
description: Use when Codex is asked to create, update, sync, or hand over Gryphon Storybook prototypes for design work. Follow the StaffAny workflow where codex/gryphon-storybook-master is the design source of truth, clean handover branches are created from develop, and accepted handover changes are synced back to master.
---

# Gryphon Storybook Prototype Handoff

## Core Rule

Use `codex/gryphon-storybook-master` as the source of truth for finalized Gryphon Storybook design prototypes.

Use clean feature handover branches from `origin/develop` for engineering review.

Never let a handover branch become the only place where the latest finalized design exists.

## Branch Roles

- `codex/gryphon-storybook-master`: Long-lived design prototype master. Use for exploration, reusable mock layouts, finalized stories, and future copy source.
- `codex/<feature>-storybook-handoff`: Short-lived engineering handover branch. Create from `origin/develop`. Keep scoped to one feature.
- `develop`: Engineering base branch. Do not prototype directly here.

## Before Prototyping

Always update the prototype master branch first.

```bash
git switch codex/gryphon-storybook-master
git pull origin codex/gryphon-storybook-master
```

Then make Storybook changes in `apps/gryphon/.storybook/stories/gryphon/...`.

Commit and push routine prototype updates directly to `codex/gryphon-storybook-master`.

```bash
git add <changed-files>
git commit -m "feat(gryphon): update <feature> storybook prototype"
git push origin codex/gryphon-storybook-master
```

Do not force-push `codex/gryphon-storybook-master`.

## Creating A Clean Handover Branch

When the design is finalized and ready for engineering, create a fresh branch from `origin/develop`.

```bash
git fetch origin develop
git switch -c codex/<feature>-storybook-handoff origin/develop
```

Copy only finalized feature files from master.

```bash
git checkout codex/gryphon-storybook-master -- apps/gryphon/.storybook/stories/gryphon/<Feature>
```

If the feature needs standalone review, add a scoped Storybook config such as:

```text
apps/gryphon/.storybook-<feature>/
```

Include a short `HANDOVER.md` with preview, build, and optional Chromatic commands.

Keep unrelated Appraisals, Design System, older prototype stories, and exploratory files out of the handover PR.

## Handover PR Standard

Open the handover PR as draft against `develop`.

The PR should:

- Contain one feature only.
- Have a clean commit history.
- Include only relevant stories, config, assets, package or lockfile changes, and handover notes.
- Build successfully with the scoped Storybook command.

Do not run or publish Chromatic unless explicitly asked.

## After Engineering Review

If engineering asks for changes in the handover PR, apply the accepted final version back to `codex/gryphon-storybook-master`.

Recommended sync pattern:

```bash
git switch codex/gryphon-storybook-master
git pull origin codex/gryphon-storybook-master
git checkout codex/<feature>-storybook-handoff -- apps/gryphon/.storybook/stories/gryphon/<Feature>
git add <changed-files>
git commit -m "chore(gryphon): sync finalized <feature> storybook prototype"
git push origin codex/gryphon-storybook-master
```

## Verification

For full master prototype changes, run:

```bash
pnpm --dir apps/gryphon run build-storybook
```

For scoped handover changes, run the feature-specific build command from `HANDOVER.md`, for example:

```bash
pnpm --dir apps/gryphon run build-storybook:approval-routing
```

Report build warnings separately from build failures.

## Team Instruction Summary

Use this summary when explaining the workflow to designers:

```md
Prototype in `codex/gryphon-storybook-master`.
Pull latest before starting.
Push finalized prototype updates back to master.
For engineering handover, create a clean branch from `develop`.
Copy only the finalized feature files from master into the handover branch.
Open a draft PR for the handover branch.
After engineering review, sync the accepted final changes back into master.
```
