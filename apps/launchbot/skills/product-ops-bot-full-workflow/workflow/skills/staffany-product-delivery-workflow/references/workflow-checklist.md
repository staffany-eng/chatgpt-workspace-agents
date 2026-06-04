# Workflow Checklist

## Preflight Gate
- [ ] `request_type` identified: `product-output` | `frontend` | `backend` | `mixed`
- [ ] Route confirmed
- [ ] Model tier per agent recorded
- [ ] Output path reserved under `outputs/<type>/`
- [ ] Jira sync mode set for Jira grooming: `direct-sync` | `md-only`
- [ ] Jira target issue recorded (`ISSUE-123`/URL or `TBD`)
- [ ] Existing Jira context read first when `direct-sync` is used
- [ ] Jira existing context reconciliation logged (`what was retained/changed`)
- [ ] Jira required fields confirmed for direct sync: `issue`, `mode`, `file`, and env vars (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`)
- [ ] Jira setup/bootstrap checked (see `references/jira-setup.md`) when direct sync is used
- [ ] PRD notion sync mode set when PRD has a target page: `direct-sync` | `full-overwrite` | `md-only`
- [ ] PRD notion target recorded (page/database URL/ID or `TBD`)
- [ ] PRD lifecycle state identified: `new` (bootstrap from template) | `existing` (iterate/update)
- [ ] If `new`, PRD page created from Notion PRD template and styling reviewed
- [ ] Notion integration access confirmed for target database/page
- [ ] PRD notion freshness checked when `direct-sync` is used
- [ ] PRD update mode logged: `add-missing-only` | `full-replace`
- [ ] RICE assessment completed for Jira grooming (Reach, Impact, Confidence, Effort, RICE Score, rationale)
- [ ] Backend-first review planned (`kraken` then `gryphon`)
- [ ] Current screen inventory checked for UX scope
- [ ] UX improvement delta defined for UX scope
- [ ] Net-new benchmark scope set (>=3 competitors) or marked N/A

## Handoff Contract (Every Transition)
- `destination_agent`
- `task_summary`
- `request_type`
- `selected_reasoning_tier`
- `source_of_truth_checked`
- `constraints`
- `acceptance_criteria_or_fix_target`
- `affected_files`
- `jira_target_ticket`
- `notion_target_document`
- `open_questions`
- `done_signal`

## Triage Direct Resolution Record (When Applicable)
- `triage_resolved_directly`: `true` | `false`
- `selected_reasoning_tier`: `Low` when direct triage is used
- `resolution_note`
- `why_no_handoff_needed`
- `done_signal`

## Completion Gate
- [ ] Output file path(s) listed
- [ ] Source-of-truth files listed
- [ ] Validation/checks listed (or skipped with reason)
- [ ] Remaining open questions listed (or `None`)
