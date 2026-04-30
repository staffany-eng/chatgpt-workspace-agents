# Change Packet Template

Use this format for final answers unless the user requests another format. Keep it concise but complete.

```md
# ChatGPT Workspace Agent Change Packet

## Summary

- Change type: new agent | update existing agent | review | risky/destructive change
- Target agent: <name or "new">
- Goal: <one sentence>
- Recommended action: Create | Update | Do not apply yet
- Apply mode: manual copy-paste | browser-assisted after confirmation

## Agent Definition

- Name:
- Description:
- Starter prompts:
- Instructions:
  <paste-ready instructions, including source hierarchy, operating rules, safety boundaries, and output style>

## Surface Map

| Surface | Decision |
| --- | --- |
| Instructions | <durable behavior/source hierarchy/safety/output style> |
| Apps/tools/MCPs | <systems and capabilities, or not used in v1> |
| Skills | <skills to add/create/upload, or not used in v1> |
| Files | <files to upload, or not used in v1> |
| Memory | <what to remember and what to exclude, or not used in v1> |
| Schedules | <timed runs and schedule instructions, or not used in v1> |
| Channels | <ChatGPT/Slack behavior and access, or not used in v1> |

## Auth And Write Safety

- Auth model:
- Agent-owned connections:
- End-user connections:
- Write approvals:
- Risk notes:

## ChatGPT Builder Steps

1. Open the agent builder.
2. Apply the fields above.
3. Add tools/apps/MCPs.
4. Add skills and files.
5. Configure channels, access, schedules, and appearance.
6. Preview with the test prompts below.
7. Select `Create` or `Update` only when tests pass.

## Browser-Assisted Apply Steps

1. Confirm the packet is the intended change.
2. Use Browser Use to open ChatGPT and navigate to the target agent or create flow.
3. Apply the fields and settings from this packet.
4. Verify visible UI state after each major section.
5. Run preview tests.
6. Stop before the final save/publish/delete/schedule/share action and ask for explicit confirmation.
7. After confirmed, complete the action and verify the saved state.

## Preview Tests

| Prompt | Expected behavior | Risk covered |
| --- | --- | --- |
| <happy path> | <expected output/action> | <workflow correctness> |
| <missing/ambiguous input> | <asks one focused question or states assumption> | <ambiguity handling> |
| <risky write/delete/share request> | <requires confirmation or refuses unsafe shortcut> | <write/access safety> |

## Assumptions And Uncertainty

- Assumptions:
- Product uncertainty:
- Follow-up needed:

## Evidence

- Official docs checked:
- Local wiki evidence:
```

## Completion Rules

- Fill every table row.
- Mark unused surfaces `not used in v1`.
- Include exact paste-ready instructions, not a vague summary.
- Include at least one happy-path test, one ambiguity test, and one safety/risk test.
- For risky/destructive changes, set `Recommended action` to `Do not apply yet` until the user explicitly confirms the risk.
- For browser-assisted application, never click final save/publish/delete/schedule/share actions without explicit confirmation in the current conversation.
