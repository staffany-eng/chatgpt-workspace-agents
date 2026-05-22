# Output Rules

## Output Directories
- Jira: `outputs/jira/`
- PRD: `outputs/prd/`
- Other docs: `outputs/docs/`

## Naming Convention
- `YYYY-MM-DD-short-kebab-title.md`
- PRD override: `YYYYMMDD - <Title> (PRD).md`

## Referencing
- Use full relative path in prompts for reliable mentions:
  - `@outputs/jira/2026-03-16-my-payroll-cp22a-grooming.md`
- Alias files can be used for convenience if maintained.

## Jira AC Style
- Single `Acceptance Criteria` section only.
- Frontend-impact statements first, backend/logic next.
- No `Frontend:`/`Backend:` prefixes.
- Keep statements concise and testable.

## Jira Sync Output Rule
- If Jira issue key/link is provided and credentials are available, run read/sync via skill-local scripts in the same run.
- Use `references/jira-sync.md` as canonical source for exact commands, modes, and flags.
- Use `md-only` output only when Jira write is blocked or user explicitly requests draft-only output.

## RICE Output Rule (Mandatory For Jira Grooming)
- Include full factors: Reach, Impact, Confidence, Effort, and computed `RICE Score`.
- Use formula: `(Reach * Impact * Confidence) / Effort`.
- Separate facts from assumptions when scoring inputs.
- If a short Jira `RICE Rationale` field is used, keep it <=255 chars and include only value plus key risk/dependency.
