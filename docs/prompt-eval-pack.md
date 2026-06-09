# Prompt Eval Pack

This repo keeps prompt evals beside each Hermes app packet:

- `apps/hermes-data-bot/tests/prompt-evals.json`
- `apps/nurtureany-sales-bot/tests/prompt-evals.json`
- `apps/launchbot/tests/prompt-evals.json`

PS WEE / PS Wee Manager prompt evals moved with the canonical PSM Ops Bot packet
to `staffany-eng/customer-360` under `apps/psm-ops-bot/tests/`.

The readable regression cases stay in Markdown. The JSON files are the machine-checkable layer for targeted prompt routing, tool trace, answer-contract, and live-smoke specs.

## Schema

Each eval case uses this shape:

```json
{
  "id": "app-lane-behavior",
  "bot": "Bot display name",
  "surface": "slack",
  "lane": "static",
  "input": "User message",
  "setup": {},
  "expected_tool_trace": {},
  "expected_answer_contract": {},
  "forbidden_behavior": [],
  "grade_notes": "How to grade this case.",
  "assertions": {
    "source_files": [
      {
        "path": "profile/SOUL.md",
        "must_contain": ["required packet text"],
        "must_not_contain": ["forbidden packet text"]
      }
    ]
  }
}
```

Supported lanes:

- `static`: first-response prompt-contract behavior, usually no live tools.
- `tool-trace`: expected tool names and forbidden substitutes.
- `answer-contract`: final response labels, caveats, and blocked/partial handling.
- `live-smoke`: specs for a later bot-owned Slack smoke. The local runner validates the spec only; it never writes Slack.

## Runner

Run from repo root:

```bash
node scripts/run-prompt-evals.mjs --app all --mode all
node scripts/run-prompt-evals.mjs --app nurtureany-sales-bot --mode tool-trace
```

The v1 runner is deterministic. It validates JSON schema, expected tool arrays, regex syntax, source-file assertions, and optional answer fixtures. It does not call a model, judge free-form output, mutate Jira, send Slack messages, or read live customer data.

## Sonnet Prompt Policy

Hermes runtime bots are Anthropic `claude-sonnet-4-6`, so prompt changes should be Sonnet-friendly:

- Keep `SOUL.md` focused on identity, source hierarchy, hard safety invariants, router shape, and output contracts.
- Move long workflow recipes into skills and runtime references.
- Use XML-style examples for high-risk paths, especially preflight, social-only answer, capability answer, blocked answer, and post-`run` final answer.
- Narrow `MUST` language to true invariants: no human-token Slack posting, no unsafe sends/writes, source hierarchy, and exact tool triggers where a past failure exists.
- Prefer structured internal routing before prose: `intent`, `source_class`, `requires_run`, `allowed_tools`, `forbidden_tools`, `confidence`, and `blocked_reason`.

Hermes source packets currently document the Sonnet route and model, but this repo does not verify a provider-level effort knob for Anthropic requests. Until the runtime exposes a confirmed knob, record effort policy in eval metadata instead of inventing config:

- `low`: capability/readiness/static answers.
- `medium`: normal Slack tool workflows.
- `high`: long multi-source research or conflict resolution.

## Codex Boundary

Codex is the change operator for this repo, not the Hermes runtime prompt target. Codex checks should verify maintainer behavior: read `AGENTS.md`, inspect app packets before editing, use source-controlled patches, run app verifiers, and summarize evidence. Do not copy Codex repo-work patterns blindly into Hermes Slack prompts.
