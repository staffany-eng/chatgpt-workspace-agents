#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../.."

npm run rev-ops-bot:verify
python3 -m unittest discover apps/rev-ops-bot/runtime/mcp -p 'test_*.py'
