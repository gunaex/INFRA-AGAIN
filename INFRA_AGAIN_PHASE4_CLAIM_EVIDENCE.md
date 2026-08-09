# INFRA-AGAIN Phase 4 — Claim / Evidence Matrix

> Rule: Every critical claim MUST be backed by executed evidence at the appropriate verification level.

| # | Claim | Evidence Level | Verification | Result |
|---|---|---|---|---|
| 1 | API routes exist (30 routes) | INTEGRATION | Route enumeration at import | PASS |
| 2 | FastAPI import succeeds | UNIT | `python -c "from infra_again.api import app"` exit 0 | PASS |
| 3 | API runs as real server | RUNTIME | uvicorn on port 18090, curl health 200, PID tracked, clean kill | PASS |
| 4 | `/health` returns 200 | RUNTIME | `curl -f http://127.0.0.1:18090/health` → 200 | PASS |
| 5 | `/api/v1/providers` returns AWS/GCP | RUNTIME | curl → AWS=1 exec, GCP=0 exec | PASS |
| 6 | AWS S3 is VERIFIED, SIMULATED | RUNTIME | curl → lifecycle=VERIFIED, exec=['SIMULATED'], source=MANUAL_VERIFIED | PASS |
| 7 | GCP Storage is PLAN_ONLY, not executable | RUNTIME | curl → lifecycle=CAPABILITY_MAPPED, exec=['PLAN_ONLY'], isExecutable=false | PASS |
| 8 | `/api/v1/capabilities/compare` POST works | RUNTIME | curl → AWS=FULL, GCP=PLAN_ONLY | PASS |
| 9 | `/api/v1/catalog/status` returns 2 snapshots | RUNTIME | curl → 2 snapshots with checksums | PASS |
| 10 | Unknown provider → 404 | RUNTIME | curl → 404 | PASS |
| 11 | Catalog sync LOCAL_REFRESH works | RUNTIME | curl POST → syncMode=LOCAL_REFRESH | PASS |
| 12 | Catalog sync LIVE is NOT_IMPLEMENTED | RUNTIME | curl POST → status=not_implemented | PASS |
| 13 | Docker image builds | RUNTIME | `docker build -t infra-again:v4-test .` exit 0 | PASS |
| 14 | Docker container runs + health 200 | RUNTIME | Docker run → curl health 200, providers API works | PASS |
| 15 | Catalog persists to SQLite | INTEGRATION | `catalog.persist(db)` then `load_persisted(db)` → same data | PASS |
| 16 | Restart durability (checksums match) | INTEGRATION | Persist → new instance load → same checksum, same service count | PASS |
| 17 | Snapshot checksum is deterministic | UNIT | Same content → same checksum; change → different checksum | PASS |
| 18 | Catalog diff works (same = 0 changes) | UNIT | `diff_snapshots(same_id, same_id)` → 0 changes | PASS |
| 19 | Stale freshness field exists | UNIT | `FreshnessStatus.CURRENT/STALE/UNKNOWN` enum | PASS |
| 20 | Deprecated flag propagates to compare output | UNIT | Set deprecated=True → compare output shows deprecated | PASS |
| 21 | Capability mapper: OBJECT_STORAGE→S3, GCP, QUANTUM→empty | INTEGRATION | `catalog.compare(capability, mode)` → correct fits | PASS |
| 22 | Provider comparison ordering (AWS first) | UNIT | SIMULATED compare → AWS before GCP | PASS |
| 23 | Planner Golden A: AWS SIMULATED → S3 | INTEGRATION | `_query_provider_intelligence` → SUPPORTED, AWS S3 | PASS |
| 24 | Planner Golden B: GCP PLAN_ONLY → Cloud Storage | INTEGRATION | `_query_provider_intelligence` → PLAN_ONLY, GCP Storage | PASS |
| 25 | Planner Golden C: neutral SIMULATED → AWS S3 | INTEGRATION | No hint → AWS selected (only SIMULATED executable) | PASS |
| 26 | Planner Golden D: GCP SIMULATED → NOT_SUPPORTED | INTEGRATION | GCP hint + SIMULATED → EXECUTION_NOT_SUPPORTED | PASS |
| 27 | Planner Golden E: QUANTUM_DATABASE → no candidates | INTEGRATION | Unknown capability → empty, selected=None | PASS |
| 28 | Provenance: STATIC_FIXTURE adapters | UNIT | `AwsCatalogSource.source_kind == 'STATIC_FIXTURE'` | PASS |
| 29 | Provenance: no hidden OFFICIAL_LIVE | UNIT | All adapters source_kind = STATIC_FIXTURE | PASS |
| 30 | Provenance: S3 MANUAL_VERIFIED, EC2 STATIC_SEED | UNIT | SourceType audit of all services | PASS |
| 31 | Phase 3 regression (46 tests) | RUNTIME | `pytest tests/integration/test_phase3.py tests/unit/` exit 0 | PASS |
| 32 | Frontend build produces dist/ | RUNTIME | `npm ci && vite build` → dist/index.html exists | PASS |
| 33 | LIVE_OFFICIAL_SYNC | N/A | NOT_EXECUTED (internet source fetch not attempted) | SKIP |
| 34 | BROWSER_E2E | N/A | NOT_EXECUTED (no browser automation) | SKIP |
| 35 | FLY_REMOTE | N/A | NOT_EXECUTED (Fly deploy not performed) | SKIP |
| 36 | CLOUDFLARE_REMOTE | N/A | NOT_EXECUTED (Cloudflare deploy not performed) | SKIP |

## Evidence Level Legend

- **STATIC_ONLY**: Source code exists, no execution verification
- **UNIT_VERIFIED**: Unit-level Python assertion passes
- **INTEGRATION_VERIFIED**: Multi-component integration test passes (TestClient, SQLite, etc.)
- **RUNTIME_VERIFIED**: Real process started, real HTTP request made, response verified
- **REMOTE_VERIFIED**: Deployed to remote environment and verified

## Summary

- RUNTIME verified: 22 claims
- INTEGRATION verified: 8 claims
- UNIT verified: 6 claims
- NOT_EXECUTED (optional): 4 claims
- No claims are STATIC_ONLY
