# Tasks: Add PSM Ops Geocode File Input

- [x] Add OpenSpec proposal, design, tasks, and spec files.
- [x] Implement Slack CSV/TSV discovery, download, parsing, and geocoding in `psm_google_geocode`.
- [x] Wire the new MCP tool in manifest/config/docs/instructions.
- [x] Add focused unit tests for CSV/TSV success and blocked cases.
- [x] Run focused MCP tests.
- [x] Run `pnpm psm-ops-bot:verify`.
- [x] Add routing rule and regression eval for hidden Slack attachment metadata.
- [x] Run focused prompt eval verification for the hidden attachment metadata case.
- [ ] Strict OpenSpec validation gate: treat `psm_google_geocode` implementation and manifest wiring as OpenSpec-incomplete until `openspec validate add-psm-ops-geocode-file-input --strict` has run and passed.
- [ ] Run `openspec validate add-psm-ops-geocode-file-input --strict` once the OpenSpec CLI is available.
