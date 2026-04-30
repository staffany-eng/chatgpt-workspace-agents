# ChatGPT Workspace Agent Build Rubric

## Evidence Used

- [ChatGPT Workspace Agent Official Docs](../sources/chatgpt-workspace-agent-docs.md) - weight 5.
- [OpenClaw Official Docs](../sources/openclaw-official-docs.md) - weight 5 for source analogies.
- [Hermes Agent Docs And Patterns](../sources/hermes-agent-docs.md) - weight 4.
- [Midas Karpathy Research Process](../sources/midas-research-process.md) - weight 5 for research process.

## Rubric

Before building a ChatGPT workspace agent, answer these:

1. Task: What repeatable workflow does the agent own?
2. Audience: Who runs it, and where: ChatGPT, Slack, schedule, or both?
3. Apps/tools: Which systems must it access?
4. Auth: Which app connections are end-user account versus agent-owned account?
5. Write safety: Which actions require confirmation?
6. Skills: Which repeatable procedures should be packaged as skills?
7. Files: Which templates, examples, policies, and source docs should be uploaded?
8. Memory: What should be remembered per user or per agent, and what should stay out?
9. Output: What artifact should the agent produce, and where should it save/send it?
10. Testing: What preview prompts, edge cases, and source fixtures prove it works?
11. Sharing: Private, link-shared, directory-published, or Slack-connected?
12. Iteration: What analytics, run reviews, or feedback loop improves it?

## Acceptance Bar

A workspace-agent plan is not decision-complete until every rubric item has a concrete answer or a deliberate "not used in v1" decision.

