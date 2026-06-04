# Source Quality

## Source Priority

Use sources in this order:

1. Official regulation text from Kementerian Keuangan/JDIH, DJP, BPK, or other government repositories.
2. Official DJP guidance, help pages, forms, press releases, and regulator articles.
3. StaffAny repository evidence for actual product behavior.
4. Tax consultant, accounting firm, vendor, news, or blog content for discovery only.

Do not use secondary sources as final authority for a regulatory claim unless no official source is available and the answer labels the limitation.

## Secondary Consultant Sources

- `hipajak_consultant_tax_knowledge_bank_2026_05` is a StaffAny user-provided workbook of Hipajak consultant answers. Use it as consultant/vendor guidance for discovery, implementation questions, and validation backlog prioritisation.
- Do not treat Hipajak consultant answers as official DJP/Coretax regulation. When a consultant answer affects customer filing, rates, eligibility, form obligation, or payment treatment, verify against DJP, Kementerian Keuangan/JDIH, BPK, or another official government source before presenting it as final.
- If Hipajak consultant guidance conflicts with StaffAny behavior, label the difference as `Consultant guidance vs StaffAny behavior` and cite both the consultant note and the local StaffAny code path.
- If Hipajak consultant guidance conflicts with an official regulation or is too terse (for example "depends" or "can you explain more"), treat the answer as `Needs follow-up`.

## Freshness Rules

- For current rates, thresholds, filing methods, deadline rules, forms, or mandatory platform changes, verify against official online sources before answering.
- For historical questions, use the source version that applies to the target tax year or effective period.
- If the latest official source cannot be verified, say `Current regulator source not verified` and lower confidence.

## Citation Rules

Every regulatory claim should cite:

- Source title.
- Publisher/regulator.
- URL.
- Effective date, tax year, or publication date when known.
- Last checked date.

Every StaffAny claim should cite:

- Local file path, model, seed/reference table, query fact, or related skill.
- Whether the statement is direct evidence or inference.

## Gap Labels

Use one of these labels when regulation and StaffAny behavior do not fully match:

- `Not implemented`: evidence shows StaffAny lacks the capability.
- `Implemented differently`: StaffAny supports the outcome through a different workflow or data model.
- `Not proven in code`: evidence is insufficient after targeted search.
- `Regulatory source stale`: the local knowledge bank may be outdated and needs official verification.
