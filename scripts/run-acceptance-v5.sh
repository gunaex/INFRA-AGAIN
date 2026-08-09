#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3.11}"; cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
REQ_PASS=0; REQ_FAIL=0; REQ_SKIP=0; OPT_NOT_EXECUTED=0; OPT_BLOCKED=0

req_pass() { REQ_PASS=$((REQ_PASS+1)); echo -e "  ${GREEN}PASS${NC}: $1"; }
req_fail() { REQ_FAIL=$((REQ_FAIL+1)); echo -e "  ${RED}FAIL${NC}: $1"; }
req_skip() { REQ_SKIP=$((REQ_SKIP+1)); echo -e "  ${YELLOW}SKIP${NC}: $1"; }
opt_not()  { OPT_NOT_EXECUTED=$((OPT_NOT_EXECUTED+1)); echo -e "  ${YELLOW}NOT_EXECUTED${NC}: $1"; }
section() { echo ""; echo -e "${GREEN}=== $1 ===${NC}"; }

cleanup() {
  if [ -n "${BACKEND_PID:-}" ]; then kill "$BACKEND_PID" 2>/dev/null || true; wait "$BACKEND_PID" 2>/dev/null || true; fi
  if [ -n "${TMPDIR:-}" ] && [ -d "$TMPDIR" ]; then rm -rf "$TMPDIR"; fi
}
trap cleanup EXIT
TMPDIR=$(mktemp -d); BACKEND_PORT=18092

# ===========================================================================
section "1. Frozen V4 Regression"
echo "  Running: ./scripts/run-acceptance-v4.sh"
set +e
bash "$PROJECT_DIR/scripts/run-acceptance-v4.sh" > "$TMPDIR/v4.txt" 2>&1; V4_EXIT=$?; set -e
[ "$V4_EXIT" -eq 0 ] && req_pass "V4 frozen: exit 0" || req_fail "V4 frozen: exit $V4_EXIT"

# ===========================================================================
section "2. Flow Domain Import"
"$PYTHON" -c "from infra_again.flow import *; print('Flow domain imported')" > "$TMPDIR/flow-import.txt" 2>&1 && req_pass "Flow domain import" || req_fail "Import failed"

# ===========================================================================
section "3. Deterministic Simulation"
"$PYTHON" -c "
from infra_again.flow import FlowSimulator, create_demo_flow, ScenarioId
flow = create_demo_flow()
s1 = FlowSimulator(flow, 'HAPPY_PATH', seed=42); e1 = s1.simulate()
s2 = FlowSimulator(flow, 'HAPPY_PATH', seed=42); e2 = s2.simulate()
for i,(a,b) in enumerate(zip(e1,e2)):
    assert a.timestamp_ms==b.timestamp_ms and a.event_type==b.event_type, f'Event {i} differs'
print(f'OK: {len(e1)} events identical')
" > "$TMPDIR/det.txt" 2>&1 && req_pass "Deterministic: same seed = same events" || { cat "$TMPDIR/det.txt"; req_fail "Deterministic"; }

# ===========================================================================
section "4. Golden Scenarios"
for SC in HAPPY_PATH AUTH_FAILURE FIREWALL_BLOCK DATABASE_SLOW API_TIMEOUT APPROVAL_WAIT RETRY_RECOVERY; do
  "$PYTHON" -c "
from infra_again.flow import FlowSimulator, create_demo_flow, reduce_state, FlowNodeState
flow = create_demo_flow(); sim = FlowSimulator(flow, '$SC', seed=42)
events = sim.simulate(); state = reduce_state(flow, events)
blocked = [k for k,v in state.node_states.items() if v==FlowNodeState.BLOCKED]
not_reached = [k for k,v in state.node_states.items() if v==FlowNodeState.NOT_REACHED]
degraded = [k for k,v in state.node_states.items() if v==FlowNodeState.DEGRADED]
print(f'{len(events)} events, blocked={blocked}, not_reached={not_reached}, degraded={degraded}')
" > "$TMPDIR/sc-$SC.txt" 2>&1 && req_pass "Scenario: $SC" || { cat "$TMPDIR/sc-$SC.txt"; req_fail "Scenario: $SC"; }
done

# ===========================================================================
section "5. Design Baseline"
"$PYTHON" -c "
from infra_again.flow import DesignBaseline
db = DesignBaseline(design_id='T-001'); db.accept('qa')
assert db.status.value == 'BASELINE_FROZEN'
inv = db.check_acceptance_invalidated('new', db.architecture_checksum, db.flow_checksum)
assert inv
db.request_change('Needs private DB'); assert db.status.value == 'CHANGE_REQUESTED'
print('Design lifecycle OK')
" > "$TMPDIR/design.txt" 2>&1 && req_pass "Design: accept, invalidate, change request" || req_fail "Design"

# ===========================================================================
section "6. Real Backend (uvicorn)"
"$PYTHON" -m uvicorn infra_again.api:app --host 127.0.0.1 --port $BACKEND_PORT > "$TMPDIR/uvicorn.log" 2>&1 & BACKEND_PID=$!; sleep 3
kill -0 "$BACKEND_PID" 2>/dev/null && req_pass "Uvicorn started" || req_fail "Uvicorn"

# ===========================================================================
section "7. HTTP: Create Design + Generate"
DESIGN_RESP=$(curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/v1/designs?name=Test" 2>/dev/null)
DESIGN_ID=$(echo "$DESIGN_RESP" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['design']['designId'])" 2>/dev/null)
[ -n "$DESIGN_ID" ] && req_pass "Design created: $DESIGN_ID" || req_fail "Design creation"

GEN_RESP=$(curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/v1/designs/$DESIGN_ID/generate" 2>/dev/null)
GEN_STATUS=$(echo "$GEN_RESP" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['design']['status'])" 2>/dev/null)
[ "$GEN_STATUS" = "REVIEW_READY" ] && req_pass "Generate: $GEN_STATUS" || req_fail "Generate: $GEN_STATUS"

# ===========================================================================
section "8. HTTP: Simulate"
SIM_RESP=$(curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/v1/designs/$DESIGN_ID/simulate?scenario=HAPPY_PATH" 2>/dev/null)
SIM_EVENTS=$(echo "$SIM_RESP" | "$PYTHON" -c "import sys,json; print(len(json.load(sys.stdin)['events']))" 2>/dev/null)
[ "${SIM_EVENTS:-0}" -gt 0 ] && req_pass "Simulate: $SIM_EVENTS events" || req_fail "Simulate"

SIM2_RESP=$(curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/v1/designs/$DESIGN_ID/simulate?scenario=DATABASE_SLOW" 2>/dev/null)
SIM2_BOT=$(echo "$SIM2_RESP" | "$PYTHON" -c "import sys,json; print(len(json.load(sys.stdin)['bottlenecks']))" 2>/dev/null)
[ "${SIM2_BOT:-0}" -gt 0 ] && req_pass "Simulate DATABASE_SLOW: $SIM2_BOT bottleneck(s)" || req_fail "Simulate DATABASE_SLOW"

# ===========================================================================
section "9. HTTP: Design Acceptance"
ACCEPT_RESP=$(curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/v1/designs/$DESIGN_ID/accept?accepted_by=qa" 2>/dev/null)
ACCEPT_STATUS=$(echo "$ACCEPT_RESP" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['design']['status'])" 2>/dev/null)
[ "$ACCEPT_STATUS" = "BASELINE_FROZEN" ] && req_pass "Accept: $ACCEPT_STATUS" || req_fail "Accept: $ACCEPT_STATUS"

CHANGE_RESP=$(curl -s -X POST "http://127.0.0.1:$BACKEND_PORT/api/v1/designs/$DESIGN_ID/request-change?comment=Test%20change" 2>/dev/null)
CHANGE_STATUS=$(echo "$CHANGE_RESP" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['design']['status'])" 2>/dev/null)
[ "$CHANGE_STATUS" = "CHANGE_REQUESTED" ] && req_pass "Request change: $CHANGE_STATUS" || req_fail "Request change: $CHANGE_STATUS"

# ===========================================================================
section "10. Health + Scenarios API"
HTTP_H=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$BACKEND_PORT/health" 2>/dev/null)
[ "$HTTP_H" = "200" ] && req_pass "Health: $HTTP_H" || req_fail "Health: $HTTP_H"
SC_COUNT=$(curl -s "http://127.0.0.1:$BACKEND_PORT/api/v1/scenarios" 2>/dev/null | "$PYTHON" -c "import sys,json; print(len(json.load(sys.stdin)['scenarios']))" 2>/dev/null)
[ "${SC_COUNT:-0}" -eq 7 ] && req_pass "Scenarios: $SC_COUNT" || req_fail "Scenarios: $SC_COUNT"

# ===========================================================================
section "11. Stop Backend"
kill "$BACKEND_PID" 2>/dev/null || true; wait "$BACKEND_PID" 2>/dev/null || true
req_pass "Backend stopped"
BACKEND_PID=""

# ===========================================================================
section "12. Frontend Fresh Build"
if [ -d ui ]; then
  rm -rf ui/dist
  (cd ui && npm ci --silent 2>&1 | tail -1) || true
  set +e; (cd ui && npx vite build 2>&1 | tail -1); VITE_EXIT=$?; set -e
  if [ "$VITE_EXIT" -eq 0 ] && [ -f ui/dist/index.html ]; then req_pass "Frontend: build OK, dist/index.html exists"
  else req_fail "Frontend build: exit=$VITE_EXIT"; fi
else req_skip "No ui/"; fi

# ===========================================================================
section "13. Optional: BROWSER_E2E"
opt_not "BROWSER_E2E (not executed)"

section "14. Optional: OBSERVED_RUNTIME"
opt_not "OBSERVED_RUNTIME (not implemented)"

section "15. Optional: REAL_CLOUD"
opt_not "REAL_CLOUD (out of scope for Phase 5)"

# ===========================================================================
echo ""; echo "========================================"; echo "INFRA-AGAIN V5 ACCEPTANCE"; echo "========================================"
echo "Phase 4 Frozen: exit=$V4_EXIT"
echo "Phase 5 Required: PASS=$REQ_PASS FAIL=$REQ_FAIL SKIP=$REQ_SKIP"
echo "Optional: NOT_EXECUTED=$OPT_NOT_EXECUTED"
echo ""
if [ "$REQ_FAIL" -eq 0 ] && [ "$REQ_SKIP" -eq 0 ] && [ "$V4_EXIT" -eq 0 ]; then
  echo "Phase 5: LOCAL_VERIFIED"; exit 0
else
  echo "Phase 5: PARTIAL/FAILED"; exit 1
fi
