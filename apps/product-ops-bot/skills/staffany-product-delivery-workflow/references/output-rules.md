# Output Rules

## Output Directories
- Jira: direct ticket update by default (no mandatory `outputs/jira/` file)
- PRD: `outputs/prd/`
- Other docs: `outputs/docs/`

## Naming Convention
- `YYYY-MM-DD-short-kebab-title.md`
- PRD override: `YYYYMMDD - <Title> (PRD).md`

## Referencing
- Use full relative path in prompts for reliable mentions:
  - `@outputs/prd/20260427 - Manual Overtime Feature (PRD).md`
- Alias files can be used for convenience if maintained.

## Jira AC Style
- Single `Acceptance Criteria` section only.
- Frontend-impact statements first, backend/logic next.
- No `Frontend:`/`Backend:` prefixes.
- Keep statements concise and testable.

## Jira Sync Output Rule
- If Jira issue key/link is provided, run direct read/update via skill-local scripts.
- Use `references/jira-sync.md` as canonical source for exact commands, modes, and flags.
- Use `md-only` only when Jira is inaccessible or user explicitly requests a markdown artifact.

## RICE Output Rule (Mandatory For Jira Grooming)
- Include full factors: Reach, Impact, Confidence, Effort, and computed `RICE Score`.
- Use formula: `(Reach * Impact * Confidence) / Effort`.
- Separate facts from assumptions when scoring inputs.
- If a short Jira `RICE Rationale` field is used, keep it <=255 chars and include only value plus key risk/dependency.
