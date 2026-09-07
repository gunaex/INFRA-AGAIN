import json

from infra_again.flow import api
from infra_again.flow.models import DesignBaseline


def test_persist_design_accepts_browser_flow_payload(tmp_path, monkeypatch):
    database = tmp_path / "infra.db"
    monkeypatch.setattr(api, "DB_PATH", str(database))
    design = DesignBaseline()
    flow = {
        "nodes": [{"id": "api", "data": {"label": "API"}}],
        "edges": [],
        "rationale": "Generated and approved by OIDA",
    }

    api._persist_design(design, flow)

    with api._get_conn() as connection:
        saved = connection.execute(
            "SELECT flow_json FROM flow_designs WHERE design_id=?", (design.design_id,)
        ).fetchone()[0]
    assert json.loads(saved) == flow
