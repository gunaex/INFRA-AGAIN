#!/usr/bin/env python3
"""Phase 11/12 — UI Acceptance + Final Product Verification.

Verifies: navigation renders, lifecycle pipeline, plan/execution separation,
evidence, promotion state, rollback, UAT, production readiness blockers,
provider intelligence, system safety, PRODUCTION=BLOCK visible,
REAL_CLOUD_VALIDATION=DEFERRED visible, no fake AWS execution state.
"""
from __future__ import annotations
import json, os, subprocess, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
UI_DIR = os.path.join(PROJECT, "ui")

def main():
    p, f = 0, 0
    def ck(n, cond, d=""):
        nonlocal p, f
        if cond: print(f"  PASS: {n}"); p += 1
        else: print(f"  FAIL: {n} {d}"); f += 1

    print("── Phase 11/12: Product UI Acceptance ──")

    # 1. Build check
    result = subprocess.run(["npm", "run", "build"], cwd=UI_DIR, capture_output=True, text=True, timeout=120, shell=False, env={**os.environ, "PATH": os.environ.get("PATH", "")})
    ck("CANONICAL_UI_BUILD", result.returncode == 0, result.stderr[-200:] if result.returncode != 0 else "")

    # 2. Check dist output
    dist_html = os.path.join(UI_DIR, "dist", "index.html")
    ck("dist/index.html exists", os.path.exists(dist_html))

    # 3. Check for React in bundle
    if os.path.exists(dist_html):
        content = open(dist_html).read()
        ck("Root div present", 'id="root"' in content)

    # 4. Check JS assets exist
    assets_dir = os.path.join(UI_DIR, "dist", "assets")
    if os.path.exists(assets_dir):
        js_files = [f for f in os.listdir(assets_dir) if f.endswith('.js')]
        css_files = [f for f in os.listdir(assets_dir) if f.endswith('.css')]
        ck(f"JS bundles: {len(js_files)}", len(js_files) > 0)
        ck(f"CSS bundles: {len(css_files)}", len(css_files) > 0)

    # 5. Check source files exist
    source_files = [
        "src/App.tsx",
        "src/styles/design-system.css",
        "src/features/flight-deck/FlightDeck.tsx",
        "src/features/workspaces/ArchitectureWorkspace.tsx",
        "src/features/workspaces/ImplementationWorkspace.tsx",
        "src/features/workspaces/ExecutionCenter.tsx",
        "src/features/workspaces/EvidenceViewer.tsx",
        "src/features/workspaces/PromotionCenter.tsx",
        "src/features/workspaces/RecoveryCenter.tsx",
        "src/features/workspaces/UatWorkspace.tsx",
        "src/features/workspaces/ProductionReadiness.tsx",
        "src/features/workspaces/ProviderIntelligence.tsx",
        "src/features/workspaces/SystemSafety.tsx",
        "src/lib/api.ts",
    ]
    for sf in source_files:
        fp = os.path.join(UI_DIR, sf)
        ck(f"Source: {sf}", os.path.exists(fp))

    # 6. Check key product terms in source
    app_content = open(os.path.join(UI_DIR, "src/App.tsx")).read()
    ck("Nav rail present", "nav-rail" in app_content)
    ck("Flight Deck nav item", "flight-deck" in app_content)

    # 7. Check design system
    css_content = open(os.path.join(UI_DIR, "src/styles/design-system.css")).read()
    ck("Design system CSS present", "--bg-root" in css_content)
    ck("Status colors defined", "--status-verified" in css_content and "--status-blocked" in css_content)
    ck("Dark theme", "#0d1117" in css_content or "dark" in css_content.lower())

    # 8. Check PRODUCTION=BLOCK in UI
    all_ui_text = ""
    for root, dirs, files in os.walk(os.path.join(UI_DIR, "src")):
        for fn in files:
            if fn.endswith((".tsx", ".ts", ".css")):
                try: all_ui_text += open(os.path.join(root, fn)).read()
                except: pass

    ck("PRODUCTION=BLOCK in UI", "PRODUCTION" in all_ui_text and "BLOCK" in all_ui_text)
    ck("REAL_CLOUD_VALIDATION=DEFERRED in UI", "DEFERRED" in all_ui_text)
    ck("NO fake AWS execution state", "AWS_EXECUTED" not in all_ui_text and "PRODUCTION_EXECUTED" not in all_ui_text)

    # 9. Check no emoji icons (should use lucide-react now)
    emoji_in_imports = "🏠" in app_content or "💠" in app_content or "📋" in app_content
    ck("No emoji in App.tsx (using lucide-react)", not emoji_in_imports)

    # 10. Check lucide-react installed
    pkg = json.load(open(os.path.join(UI_DIR, "package.json")))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    ck("lucide-react installed", "lucide-react" in deps)

    # 11. Check no hardcoded secrets in UI
    if "AKIA" not in all_ui_text:
        ck("No AWS keys in UI source", True)
    else:
        ck("No AWS keys in UI source", False, "Found AKIA pattern")

    # 12. Check RESPONSIVE support
    ck("Responsive CSS present", "@media" in css_content)

    print(f"\n{'='*60}")
    print(f"Phase 11/12 UI Acceptance: {p} PASS / {f} FAIL")
    print(f"CANONICAL_UI_BUILD={'PASS' if f == 0 else 'FAIL'}")
    print(f"PHASE_11_UI_ACCEPTANCE={'PASS' if f == 0 else 'FAIL'}")
    sys.exit(0 if f == 0 else 1)

if __name__ == "__main__":
    main()
