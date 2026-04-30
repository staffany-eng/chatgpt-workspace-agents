---
name: staffany-data-bot-memory-learning
display_name: staffany-data-bot-memory-learning
description: Use when Da Ta Bot receives feedback, corrections, preferred terminology, metric definitions, output preferences, or repeated question patterns that may be worth storing as long-term memory for future StaffAny BigQuery, Pantheon, or Slack-thread data work.
short_description: Confirm reusable Da Ta Bot learning before memory storage.
default_prompt: Use $staffany-data-bot-memory-learning to decide whether Da Ta Bot should remember feedback or a metric definition.
---

# StaffAny Da Ta Bot Memory Learning

Use this skill when the user gives feedback or a correction that may improve future Da Ta Bot answers.

## What To Remember

Store only reusable learning:

- Confirmed metric definitions.
- Confirmed StaffAny terminology mappings.
- Preferred output formats.
- Repeated feedback patterns.
- Stable instructions about how Kai Yi wants Da Ta Bot to answer future StaffAny data questions.

## What Not To Remember

Never store:

- Secrets, OAuth credentials, connector tokens, API keys, private keys, or session credentials.
- Raw Slack transcripts, Slack images, copied thread contents, or one-off screenshots.
- Raw BigQuery results, row-level customer data, PII, bank details, NRIC/FIN, phone numbers, employee-level payroll detail, or sensitive support context.
- One-off task details that do not improve future runs.
- Ambiguous feedback that Kai Yi has not confirmed.

## Workflow

1. Classify the feedback.
   - If it is a reusable preference, metric definition, or terminology mapping, continue.
   - If it is one-off context, use it for the current answer but do not store it.
   - If it contains excluded sensitive content, do not store it.
2. Decide whether the feedback is clear enough.
   - If clear and low-risk, ask a short confirmation before storing.
   - If ambiguous, interview Kai Yi with one focused question that resolves the ambiguity.
   - If conflicting with existing memory or uploaded files, ask which rule should win.
3. Store a distilled memory only after confirmation.
   - Store the rule, not the raw transcript.
   - Include the minimum useful scope, for example metric name, default field, grain, and caveat.
   - Do not store examples containing real StaffAny organization names, Slack content, or query result rows unless Kai Yi explicitly says they are safe and reusable.
4. Acknowledge the stored memory briefly.
   - State the remembered rule in one sentence.
   - If not stored, state that it was used for the current task only.

## Memory Sentence Patterns

Use precise, future-facing memory:

```text
Kai Yi uses "active StaffAny staff" to mean StaffAny staff with org_user_status = ACTIVE unless another definition is specified.
```

```text
For Da Ta Bot answers, Kai Yi prefers an aggregate result first, followed by organization and activity breakdowns when useful.
```

Avoid raw or vague memory:

```text
Kai Yi asked about the Acme Slack thread screenshot today.
```

```text
The user likes detailed data.
```
