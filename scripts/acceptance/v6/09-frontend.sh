#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"
START=$(date +%s)
[ ! -d ui ] && { echo "SKIP"; exit 0; }
rm -rf ui/dist
(cd ui && npm ci --silent 2>&1) > "$1/npm-ci.log" 2>&1 || { echo "FAIL: npm ci"; exit 1; }
(cd ui && npx vite build 2>&1) > "$1/vite-build.log" 2>&1 || { echo "FAIL: vite build"; exit 1; }
[ ! -f ui/dist/index.html ] && { echo "FAIL: dist missing"; exit 1; }
echo "PASS $(($(date +%s)-START))s"
