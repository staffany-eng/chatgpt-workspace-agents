# ChatGPT Workspace Agent Official Docs Raw Record

## Source Metadata

- Type: official OpenAI and OpenAI Help Center docs cluster
- Source class: ChatGPT workspace agents
- Date checked: 2026-04-30
- Privacy: public docs

## Raw Content Policy

This record stores source URLs, retrieval metadata, and short citation-safe extracts. It does not copy full official docs pages.

## Source Inventory

- Workspace agents help: `https://help.openai.com/en/articles/20001143-chatgpt-workspace-agents-for-enterprise-and-business`
- ChatGPT skills help: `https://help.openai.com/en/articles/20001066-skills-in-chatgpt`
- Workspace-agent cookbook: `https://developers.openai.com/cookbook/articles/chatgpt-agents-sales-meeting-prep`
- Apps SDK state management: `https://developers.openai.com/apps-sdk/build/state-management`
- Apps SDK security/privacy: `https://developers.openai.com/apps-sdk/guides/security-privacy`
- Apps SDK MCP compatibility: `https://developers.openai.com/apps-sdk/mcp-apps-in-chatgpt`
- Codex best practices: `https://developers.openai.com/codex/learn/best-practices`

## Evidence Extracts

- ChatGPT workspace agents are for repeatable tasks and workflows in ChatGPT; they can be created, tested before publishing, connected to apps and tools, shared with the workspace, used in Slack, and scheduled.
- The agent builder can add tools, apps, custom MCPs, skills, and files.
- ChatGPT channel settings control access, schedules, description, starter prompts, and appearance.
- Workspace-agent app connections can use end-user accounts or agent-owned accounts; service accounts and least privilege are recommended for shared agent-owned access.
- Write actions default to asking during an agent run, and risky workflows should use write action safety.
- Skills are reusable workflows that can bundle instructions, examples, resources, and code; OpenAI skills follow the Agent Skills open standard but do not yet sync across products.
- ChatGPT workspace agents support version history, analytics, duplication, deletion, Slack channels, and organization directory publishing.
- Apps SDK state guidance separates authoritative business data, ephemeral UI state, and durable cross-session state.
- Apps SDK security guidance emphasizes least privilege, explicit user consent, server-side validation, audit logs, redaction, retention policy, and human confirmation for irreversible operations.
- The workspace-agent cookbook shows an agent using apps, skills, memory, testing, schedules, sharing, and per-user versus agent-owned connector behavior.

## First-Pass Learning

ChatGPT workspace agents provide product-level surfaces that map well to the corpus question: apps/tools/custom MCPs, skills, files, memory, schedules, Slack, access, auth type, write approvals, version history, and analytics. These should be the target abstraction surfaces for final plans.

