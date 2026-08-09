"""Infra Pulse + Design Review API Routes.

Phase 5: Design lifecycle, flow simulation, acceptance baseline.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .models import (
    DesignBaseline, DesignStatus, FlowDefinition, FlowPlaybackState,
    ScenarioId, MetricSource, SimulationMode, FlowEvent,
)
from .simulator import FlowSimulator, create_demo_flow
from .reducer import reduce_state

# ============================================================================
# In-memory stores (Phase 5 local-only)
# ============================================================================

_designs: dict[str, DesignBaseline] = {}
_flows: dict[str, FlowDefinition] = {}
_simulations: dict[str, dict[str, Any]] = {}


def register_flow_routes(app: FastAPI) -> None:
    """Register all Phase 5 flow/design routes on an existing FastAPI app."""

    # ------------------------------------------------------------------
    # Designs
    # ------------------------------------------------------------------

    @app.get("/api/v1/designs")
    async def list_designs():
        return {"designs": [d.to_dict() for d in _designs.values()], "count": len(_designs)}

    @app.post("/api/v1/designs")
    async def create_design(name: str = "", description: str = ""):
        design = DesignBaseline(
            design_id=f"DESIGN-{len(_designs)+1:06d}",
        )
        design.metadata = {"name": name, "description": description}
        _designs[design.design_id] = design
        return {"design": design.to_dict()}

    @app.get("/api/v1/designs/{design_id}")
    async def get_design(design_id: str):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        return {"design": d.to_dict()}

    @app.post("/api/v1/designs/{design_id}/generate")
    async def generate_design(design_id: str):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")

        # Create demo flow for this design
        flow = create_demo_flow()
        flow.architecture_graph_id = design_id
        _flows[flow.flow_id] = flow

        # Compute checksums
        d.requirements_checksum = hashlib.sha256(
            json.dumps({"designId": design_id}, sort_keys=True).encode()
        ).hexdigest()[:16]
        d.architecture_checksum = hashlib.sha256(
            json.dumps([n.to_dict() for n in flow.nodes], sort_keys=True).encode()
        ).hexdigest()[:16]
        d.flow_checksum = hashlib.sha256(
            json.dumps([e.to_dict() for e in flow.edges], sort_keys=True).encode()
        ).hexdigest()[:16]
        d.status = DesignStatus.REVIEW_READY

        return {
            "design": d.to_dict(),
            "flow": flow.to_dict(),
        }

    @app.get("/api/v1/designs/{design_id}/architecture")
    async def get_design_architecture(design_id: str):
        flows = [f for f in _flows.values() if f.architecture_graph_id == design_id]
        if not flows:
            raise HTTPException(status_code=404, detail="No flows for this design")
        return {"designId": design_id, "flows": [f.to_dict() for f in flows]}

    @app.get("/api/v1/designs/{design_id}/flows")
    async def get_design_flows(design_id: str):
        flows = [f for f in _flows.values() if f.architecture_graph_id == design_id]
        return {"designId": design_id, "flows": [f.to_dict() for f in flows], "count": len(flows)}

    @app.post("/api/v1/designs/{design_id}/simulate")
    async def simulate_design(design_id: str, scenario: str = "HAPPY_PATH", flow_id: str = "", seed: int = 42):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")

        flow = _flows.get(flow_id) if flow_id else None
        if not flow:
            flows = [f for f in _flows.values() if f.architecture_graph_id == design_id]
            flow = flows[0] if flows else None
        if not flow:
            raise HTTPException(status_code=404, detail="No flow for this design. Call /generate first.")

        sim = FlowSimulator(flow=flow, scenario=scenario, seed=seed)
        events = sim.simulate()
        bottlenecks = sim.get_bottlenecks()
        final_state = reduce_state(flow, events, bottlenecks=bottlenecks)

        sim_id = f"sim-{design_id}-{scenario}-{seed}"
        sim_result = {
            "simulationId": sim_id,
            "designId": design_id,
            "flowId": flow.flow_id,
            "scenario": scenario,
            "source": "SIMULATED",
            "durationMs": events[-1].timestamp_ms if events else 0,
            "events": [e.to_dict() for e in events],
            "bottlenecks": [b.to_dict() for b in bottlenecks],
            "finalState": final_state.to_dict(),
        }
        _simulations[sim_id] = sim_result
        return sim_result

    @app.post("/api/v1/designs/{design_id}/accept")
    async def accept_design(design_id: str, accepted_by: str = ""):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        if d.status not in (DesignStatus.REVIEW_READY, DesignStatus.USER_REVIEW):
            raise HTTPException(status_code=400, detail=f"Cannot accept design in status {d.status.value}")
        d.accept(accepted_by)
        return {"design": d.to_dict(), "note": "No real infrastructure will be created by this action."}

    @app.post("/api/v1/designs/{design_id}/request-change")
    async def request_change(design_id: str, comment: str = "", node_id: str = "", severity: str = "INFO"):
        d = _designs.get(design_id)
        if not d:
            raise HTTPException(status_code=404, detail="Design not found")
        d.request_change(comment, node_id, severity)
        return {"design": d.to_dict()}

    # ------------------------------------------------------------------
    # Flows
    # ------------------------------------------------------------------

    @app.get("/api/v1/flows/{flow_id}")
    async def get_flow(flow_id: str):
        flow = _flows.get(flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        return {"flow": flow.to_dict()}

    @app.get("/api/v1/flows/{flow_id}/events")
    async def get_flow_events(flow_id: str, scenario: str = "HAPPY_PATH", seed: int = 42):
        flow = _flows.get(flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        sim = FlowSimulator(flow=flow, scenario=scenario, seed=seed)
        events = sim.simulate()
        return {"flowId": flow_id, "scenario": scenario, "events": [e.to_dict() for e in events]}

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    @app.get("/api/v1/scenarios")
    async def list_scenarios():
        from .simulator import SCENARIO_CONFIG
        return {
            "scenarios": [
                {"id": sid, "description": cfg["description"]}
                for sid, cfg in SCENARIO_CONFIG.items()
            ]
        }
