from fastapi.testclient import TestClient

import src.api as api
from src.agent.state import IncidentReport


client = TestClient(api.app)


class FakeGraph:
    def invoke(self, state, config):
        if state["incident_id"] == "INC-404":
            raise FileNotFoundError("Incident does not exist: INC-404")

        return {"report": IncidentReport(incident_id=state["incident_id"], affected_service="checkout-api", fault_type="unknown", root_cause="Database pool exhaustion.", confidence=0.9, evidence=["metric-001"], recommended_actions=["Restore the pool size."])}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_investigation_returns_report(monkeypatch):
    monkeypatch.setattr(api, "graph", FakeGraph())
    response = client.post("/investigations", json={"incident_id": "INC-001"})

    assert response.status_code == 200
    assert response.json()["incident_id"] == "INC-001"
    assert response.json()["fault_type"] == "unknown"


def test_investigation_validates_incident(monkeypatch):
    monkeypatch.setattr(api, "graph", FakeGraph())

    assert client.post("/investigations", json={"incident_id": "bad/id"}).status_code == 422
    assert client.post("/investigations", json={"incident_id": "INC-404"}).status_code == 404
