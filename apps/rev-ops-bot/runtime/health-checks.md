# RevOps Bot Health Checks

Run packet verification from the repo root:

```bash
npm run rev-ops-bot:verify
```

Run MCP unit tests:

```bash
python3 -m unittest discover apps/rev-ops-bot/runtime/mcp -p 'test_*.py'
```

Runtime check:

```bash
apps/rev-ops-bot/runtime/check-health.sh
```
