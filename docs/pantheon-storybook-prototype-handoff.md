# Pantheon Storybook Prototype And Engineering Handover Workflow

Use this instruction file when asking Codex or Claude to work on Pantheon Storybook prototypes across Gryphon, Pixie, or other Pantheon apps.

## Team Rule

`codex/pantheon-storybook-master` is the design source of truth.

Clean handover PRs are separate, short-lived branches created from `develop`.

Any final changes made during engineering review must be synced back into `codex/pantheon-storybook-master`.

## App Scope

This workflow applies to:

- Gryphon web Storybook prototypes, usually under `apps/gryphon/.storybook/stories/...`
- Pixie mobile Storybook prototypes, usually under `apps/pixie/.storybook/stories/...` or the closest existing Pixie Storybook path
- Future Pantheon app Storybook prototypes

If the path differs, inspect the app first and follow the existing Storybook pattern.

## Workflow

### 1. Start From The Latest Prototype Master

Before making Storybook changes:

```bash
git switch codex/pantheon-storybook-master
git pull origin codex/pantheon-storybook-master
```

Do not force-push this branch.

### 2. Prototype In Master

Add or update design prototype stories in the relevant app:

```text
apps/gryphon/.storybook/stories/...
apps/pixie/.storybook/stories/...
```

Commit and push normal prototype updates directly to master:

```bash
git add <changed-files>
git commit -m "feat(storybook): update <feature> prototype"
git push origin codex/pantheon-storybook-master
```

### 3. Create A Clean Handover Branch

When the design is ready for engineering review:

```bash
git fetch origin develop
git switch -c codex/<feature>-storybook-handoff origin/develop
```

Copy only the finalized feature files from master:

```bash
git checkout codex/pantheon-storybook-master -- apps/<app>/.storybook/stories/<Feature>
```

If needed, add a scoped Storybook config:

```text
apps/<app>/.storybook-<feature>/
```

Add a short `HANDOVER.md` with:

- Local preview command
- Static build command
- Optional Chromatic command, only if requested
- List of included stories

### 4. Open Draft PR For Engineering

Open the handover PR against `develop`.

The PR should:

- Include one feature only
- Exclude unrelated Appraisals, Design System, old experiments, and other feature stories unless explicitly in scope
- Have a clean commit history
- Include only relevant stories, config, assets, package or lockfile changes, and handover notes
- Pass the relevant app or scoped Storybook build

Do not publish Chromatic unless explicitly asked.

### 5. Sync Engineering Changes Back To Master

If engineering asks for changes in the handover PR, sync the final accepted version back:

```bash
git switch codex/pantheon-storybook-master
git pull origin codex/pantheon-storybook-master
git checkout codex/<feature>-storybook-handoff -- apps/<app>/.storybook/stories/<Feature>
git add <changed-files>
git commit -m "chore(storybook): sync finalized <feature> prototype"
git push origin codex/pantheon-storybook-master
```

## Copy-Paste Prompt For Codex Or Claude

```md
Please follow the Pantheon Storybook prototype handover workflow:

1. Treat `codex/pantheon-storybook-master` as the design source of truth for Gryphon, Pixie, and other Pantheon Storybook prototypes.
2. Before prototyping, switch to master and pull latest.
3. Commit finalized prototype updates back to master.
4. For engineering handover, create a clean branch from `origin/develop`.
5. Copy only the finalized feature stories/assets/config from master into the handover branch.
6. Keep unrelated Appraisals, Design System, old experiments, and other feature stories out of the handover PR unless explicitly in scope.
7. Open the handover PR as draft against `develop`.
8. If engineering requests changes, sync the accepted final version back into `codex/pantheon-storybook-master`.
9. Do not force-push `codex/pantheon-storybook-master`.
10. Do not publish Chromatic unless explicitly asked.
```

## Quick Summary

```text
Master = design source of truth for Pantheon Storybook prototypes.
Handover branch = clean scoped copy for engineering.
Engineering review changes = sync back to master.
```
