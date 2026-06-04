---
name: indonesia-tax-knowledge-updater
description: Update and validate the Indonesia payroll tax knowledge bank used by $indonesia-payroll-tax-advisor. Use when asked to add, refresh, verify, or store regulator information for PPh21, TER, PTKP, DTP, SPT Masa PPh 21/26, e-Bupot 21/26, bukti potong, annual SPT forms, 1721-A1/B1, or StaffAny Indonesia tax/reporting mappings.
---

# Indonesia Tax Knowledge Updater

## Purpose

Maintain the knowledge bank for `$indonesia-payroll-tax-advisor` so StaffAny teammates can reuse verified Indonesia payroll tax and reporting facts. This skill updates source metadata, adds concise reference notes, and validates that every stored source has enough provenance.

Target knowledge bank:

- `skills/indonesia-payroll-tax-advisor/references/regulations.yml`
- `skills/indonesia-payroll-tax-advisor/references/pph21.md`
- `skills/indonesia-payroll-tax-advisor/references/reporting.md`
- `skills/indonesia-payroll-tax-advisor/references/source-quality.md`

Add a new reference file only when the topic does not fit the existing files, for example `annual-spt.md` for 1770/1770S/1770SS and 1721-A1/B1 distinctions.

## Guardrails

- Verify current regulator facts against official sources before writing them into the knowledge bank.
- Prefer official regulator sources: DJP, Kementerian Keuangan/JDIH, BPK regulation pages, and other Indonesian government repositories.
- Use secondary sources only to discover official references; do not store them as authoritative unless clearly marked `secondary`.
- Do not overwrite existing knowledge without preserving historical context when rules are time-bound or superseded.
- Keep reference files concise. Store detailed legal text as source links and short interpretations, not long copied passages.
- Separate regulatory facts from StaffAny behavior. StaffAny behavior must cite local code, a related skill, or a verified repo search.

## Update Workflow

1. Classify the requested update.
- `New source`: add a regulator source to `regulations.yml`.
- `New topic`: add a short section to an existing Markdown reference, or create one new topic file.
- `Refresh`: update `last_checked`, status, confidence, or notes after re-verifying the source.
- `StaffAny mapping`: add product/code mapping notes after repo evidence is checked.

2. Verify source facts.
- Browse official sources for latest/current facts when dates, forms, rates, or obligations may have changed.
- Record source title, publisher, URL, effective period, last checked date, topics, status, confidence, and notes.
- If only a placeholder source is known, mark `status: "placeholder"` and do not present it as verified.

3. Update files.
- Add or update entries in `regulations.yml` first.
- Add concise interpretation notes in the relevant Markdown reference file.
- Add cross-links from `SKILL.md` or existing reference files if a new reference file is created.

4. Validate.
- Run:
```bash
ruby skills/indonesia-tax-knowledge-updater/scripts/validate_knowledge_bank.rb
```
- Fix missing required fields, duplicate IDs, invalid confidence/status values, and broken expected reference files.

5. Report changes.
- Summarize sources added/refreshed.
- List references updated.
- State which facts were official-source verified and which remain placeholders.

## Required Source Fields

Every `regulations.yml` entry must include:

- `id`
- `title`
- `publisher`
- `regulator_type`
- `url`
- `effective_period`
- `last_checked`
- `topics`
- `status`
- `confidence`
- `notes`

Use ISO dates for `last_checked`: `YYYY-MM-DD`.

## Starter Prompts

- `Use $indonesia-tax-knowledge-updater to store the verified DJP distinction between SPT 1770, 1770S, 1770SS, and 1721-A1.`
- `Use $indonesia-tax-knowledge-updater to refresh e-Bupot 21/26 sources in the Indonesia tax knowledge bank.`
- `Use $indonesia-tax-knowledge-updater to add a StaffAny mapping note for an Indonesia payroll tax reporting feature.`
