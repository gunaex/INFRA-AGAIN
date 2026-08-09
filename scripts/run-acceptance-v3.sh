#!/usr/bin/env bash
# INFRA-AGAIN Phase 3 Accelerated Acceptance Runner
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

PYTHON="${PYTHON:-python3.11}"
command -v "$PYTHON" &>/dev/null || PYTHON="$(command -v python3 || echo '')"
[ -z "$PYTHON" ] && { echo -e "${RED}FAIL: python3${NC}"; exit 1; }

echo -e "${GREEN}INFRA-AGAIN Phase 3 Acceptance${NC}"
echo "Python: $($PYTHON --version)"

# ---------------------------------------------------------------------------
# 1. Start runtimes
# ---------------------------------------------------------------------------
FAKECLOUD_PID=""
KIND_CLUSTER="ia-accept-v3"

cleanup() {
    [ -n "$FAKECLOUD_PID" ] && kill "$FAKECLOUD_PID" 2>/dev/null || true
    kind delete cluster --name "$KIND_CLUSTER" 2>/dev/null || true
}
trap cleanup EXIT

# Start fakecloud
FAKECLOUD_BIN="${FAKECLOUD_BIN:-$(command -v fakecloud || echo '')}"
if [ -n "$FAKECLOUD_BIN" ]; then
    lsof -ti :4566 &>/dev/null && kill "$(lsof -ti :4566)" 2>/dev/null || true
    sleep 1
    "$FAKECLOUD_BIN" &>/tmp/fc-v3.log &
    FAKECLOUD_PID=$!
    for i in $(seq 1 20); do
        curl -s http://localhost:4566/_fakecloud/health &>/dev/null && break
        sleep 1
    done
    echo -e "${GREEN}OK:${NC} fakecloud"
fi

# Start kind cluster
if command -v kind &>/dev/null; then
    kind delete cluster --name "$KIND_CLUSTER" 2>/dev/null || true
    kind create cluster --name "$KIND_CLUSTER" 2>&1 | tail -1
    echo -e "${GREEN}OK:${NC} kind cluster"
fi

cd "$PROJECT_DIR"

# ---------------------------------------------------------------------------
# 2. Run tests
# ---------------------------------------------------------------------------
echo ""; echo "=== Tests ==="; echo ""
EXIT=0
"$PYTHON" -m pytest tests/ --tb=short -q 2>&1 || EXIT=$?

echo ""
if [ "$EXIT" -eq 0 ]; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL (exit=$EXIT)${NC}"
fi
exit $EXIT
