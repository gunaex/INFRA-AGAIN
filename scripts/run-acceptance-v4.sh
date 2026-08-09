#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"; PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3.11}"; command -v "$PYTHON" &>/dev/null || PYTHON="$(command -v python3 || echo '')"
echo "INFRA-AGAIN Phase 4 Acceptance"; echo ""
cd "$PROJECT_DIR"; FAIL=0

echo "=== Provider Intelligence ==="
"$PYTHON" -c "
from infra_again.intelligence.catalog import ProviderCatalog, CatalogLifecycle, ExecutionSupport, get_catalog
c = get_catalog()
assert len(c.get_services('AWS')) >= 10
assert len(c.get_services('GCP')) >= 8
s3 = c.get_service('AWS','s3')
assert s3.lifecycle == CatalogLifecycle.VERIFIED
assert 'SIMULATED' in s3.execution_support
m = c.compare('OBJECT_STORAGE')
assert len(m) >= 2
snap = c.get_snapshot('AWS')
assert snap.service_count >= 10
assert snap.checksum
print(f'OK: AWS={len(c.get_services(\"AWS\"))} GCP={len(c.get_services(\"GCP\"))} snapshots={len(c.get_snapshots())}')
" 2>&1 && echo "PASS: Provider Intelligence" || { echo "FAIL"; FAIL=1; }

echo "=== API ==="
"$PYTHON" -c "
from infra_again.api import app; from fastapi.testclient import TestClient
c = TestClient(app)
assert c.get('/api/v1/providers').status_code == 200
assert c.get('/api/v1/providers/AWS/services').status_code == 200
assert c.get('/api/v1/capabilities').status_code == 200
r = c.post('/api/v1/capabilities/compare',json={'capability':'OBJECT_STORAGE'})
assert r.status_code == 200
assert len(r.json()['candidates']) >= 2
assert c.get('/api/v1/catalog/status').status_code == 200
print('API: OK')
" 2>&1 && echo "PASS: API" || { echo "FAIL: API"; FAIL=1; }

echo "=== UI ==="
if [ -d ui ]; then (cd ui && npx vite build 2>&1 | tail -1) && echo "PASS: UI" || echo "FAIL: UI"; fi

echo ""; [ "$FAIL" -eq 0 ] && echo "ACCEPTED" || echo "PARTIAL/FAILED"
exit $FAIL
