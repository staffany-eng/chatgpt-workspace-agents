# Evidence Weights

Evidence weights decide how far a learning can travel.

| Source type | Default weight |
| --- | ---: |
| Official ChatGPT/OpenAI workspace-agent docs | 5 |
| Official OpenClaw docs | 5 |
| Midas research-process files | 5 |
| Kai Yi's deployed `openclaw-kaiyi` implementation evidence | 5 for current-state audit, 3 for general design claims |
| Hermes official repo/docs | 4 |
| Historical or local implementation artifact that may be stale | 3 |
| General ecosystem commentary or analogy | 1 |

## Promotion Rules

- `1-2`: observation only.
- `3`: weak hypothesis or implementation prompt.
- `4`: planning guidance with caveat.
- `5`: candidate decision if not contradicted by stronger or newer evidence.

## Modifiers

- `+1` if repeated across at least three independent sources.
- `+1` if backed by working implementation evidence.
- `-1` if source context differs materially from ChatGPT workspace agents.
- `-1` if the evidence is stale or likely product-version dependent.
- `-2` if contradicted by official product docs.

Do not raise final weight above `5` or below `1`.

