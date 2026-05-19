---
name: pantheon-storybook-prototype-handoff
description: Use when Codex is asked to create, update, sync, or hand over Pantheon Storybook prototypes for design work across Gryphon, Pixie, or other Pantheon apps. Follow the StaffAny workflow where codex/pantheon-storybook-master is the design source of truth, clean handover branches are created from develop, and accepted handover changes are synced back to master.
---

# Pantheon Storybook Prototype Handoff

## Core Rule

Use `codex/pantheon-storybook-master` as the source of truth for finalized Pantheon Storybook design prototypes.

Use clean feature handover branches from `origin/develop` for engineering review.

Never let a handover branch become the only place where the latest finalized design exists.

## App Scope

This workflow applies to Pantheon Storybook prototypes across apps, including:

- Gryphon web stories under `apps/gryphon/.storybook/stories/...`
- Pixie mobile stories under `apps/pixie/.storybook/stories/...`, or the closest existing Pixie Storybook path in the repo
- Any future Pantheon app Storybook prototype path

When the exact app Storybook path differs, inspect the repo first with `rg --files` or `find` and follow the app's existing Storybook conventions.

## Branch Roles

- `codex/pantheon-storybook-master`: Long-lived design prototype master. Use for exploration, reusable mock layouts, finalized stories, and future copy source across Gryphon and Pixie.
- `codex/<feature>-storybook-handoff`: Short-lived engineering handover branch. Create from `origin/develop`. Keep scoped to one feature.
- `develop`: Engineering base branch. Do not prototype directly here.

## Before Prototyping

Always update the prototype master branch first.

```bash
git switch codex/pantheon-storybook-master
git pull origin codex/pantheon-storybook-master
```

Then make Storybook changes in the relevant app, for example:

```text
apps/gryphon/.storybook/stories/...
apps/pixie/.storybook/stories/...
```

Commit and push routine prototype updates directly to `codex/pantheon-storybook-master`.

```bash
git add <changed-files>
git commit -m "feat(storybook): update <feature> prototype"
git push origin codex/pantheon-storybook-master
```

Do not force-push `codex/pantheon-storybook-master`.

## Creating A Clean Handover Branch

When the design is finalized and ready for engineering, create a fresh branch from `origin/develop`.

```bash
git fetch origin develop
git switch -c codex/<feature>-storybook-handoff origin/develop
```

Copy only finalized feature files from master.

```bash
git checkout codex/pantheon-storybook-master -- apps/<app>/.storybook/stories/<Feature>
```

If the feature needs standalone review, add a scoped Storybook config such as:

```text
apps/<app>/.storybook-<feature>/
```

Include a short `HANDOVER.md` with preview, build, and optional Chromatic commands.

Keep unrelated Appraisals, Design System, older prototype stories, and exploratory files out of the handover PR unless they are explicitly part of the feature scope.

## Handover PR Standard

Open the handover PR as draft against `develop`.

The PR should:

- Contain one feature only.
- Have a clean commit history.
- Include only relevant stories, config, assets, package or lockfile changes, and handover notes.
- Build successfully with the relevant app or scoped Storybook command.

Do not run or publish Chromatic unless explicitly asked.

## After Engineering Review

If engineering asks for changes in the handover PR, apply the accepted final version back to `codex/pantheon-storybook-master`.

Recommended sync pattern:

```bash
git switch codex/pantheon-storybook-master
git pull origin codex/pantheon-storybook-master
git checkout codex/<feature>-storybook-handoff -- apps/<app>/.storybook/stories/<Feature>
git add <changed-files>
git commit -m "chore(storybook): sync finalized <feature> prototype"
git push origin codex/pantheon-storybook-master
```

## Verification

For full master prototype changes, run the relevant app Storybook build, for example:

```bash
pnpm --dir apps/gryphon run build-storybook
pnpm --dir apps/pixie run build-storybook
```

For scoped handover changes, run the feature-specific build command from `HANDOVER.md`, for example:

```bash
pnpm --dir apps/gryphon run build-storybook:approval-routing
```

Report build warnings separately from build failures.

## Team Instruction Summary

Use this summary when explaining the workflow to designers:

```md
Prototype in `codex/pantheon-storybook-master`.
Pull latest before starting.
Push finalized prototype updates back to master.
For engineering handover, create a clean branch from `develop`.
Copy only the finalized feature files from master into the handover branch.
Open a draft PR for the handover branch.
After engineering review, sync the accepted final changes back into master.
```
