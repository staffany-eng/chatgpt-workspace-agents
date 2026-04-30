# Agent Builder Product Compass

This repo helps us design and iterate ChatGPT workspace agents using evidence from mature agent systems.

## Purpose

Agent Builder should answer one practical question: how should a ChatGPT workspace agent be structured so it can do repeatable work reliably, safely, and with the right abstraction boundaries?

The first output is not a finished agent. It is a research-backed planning corpus that can later produce agent templates, skills, connector choices, memory rules, and build rubrics.

## Current Thesis

A good workspace agent needs five separated surfaces:

- Instructions: stable role, operating rules, safety boundaries, and source-of-truth hierarchy.
- Apps and tools: connector access and custom MCPs for external systems.
- Skills: repeatable procedures, output formats, and local workflow knowledge.
- Files: durable reference material, examples, templates, and shared knowledge.
- Memory: personal or per-user continuity that should not be confused with public instructions.

OpenClaw and Hermes are implementation-rich systems. ChatGPT workspace agents have a different product surface, so this corpus should synthesize patterns rather than copy file structures blindly.

## Source Priority

1. Official ChatGPT/OpenAI docs for ChatGPT workspace-agent behavior.
2. Official OpenClaw docs for OpenClaw design intent.
3. Hermes official repo/docs for alternate architecture patterns.
4. Midas for the research wiki and Karpathy-style ingestion process.
5. `openclaw-kaiyi` for Kai Yi's current local implementation patterns and gaps.

## Current Guardrails

- Do not promote one system's implementation detail as universal product truth.
- Keep evidence, synthesis, and decisions separate.
- Treat public web docs as citation sources, not content to copy wholesale.
- Do not ingest secrets, `.env` values, API keys, OAuth tokens, or raw private credentials.
- Keep `openclaw-kaiyi` memory content private and summarize structure unless the research question requires content-level inspection.

## Known Unknowns

- Which ChatGPT workspace-agent features are available in Kai Yi's workspace right now.
- How much memory behavior is configurable in ChatGPT workspace agents beyond the product UI.
- Whether the final agent should ship as one workspace agent, several agents, shared skills, or a repo of templates.
- Which team workflows should be first-class: research ingestion, QBR briefs, operational triage, code planning, or customer setup.

