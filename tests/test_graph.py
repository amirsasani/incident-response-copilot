from langchain_core.messages import AIMessage

from src.agent.graph import build_incident_graph
from src.agent.state import IncidentReport


class FakeInvestigationModel:
    def __init__(self):
        self.call_count = 0

    def invoke(self, messages):
        self.call_count += 1

        if self.call_count == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_logs",
                        "args": {"incident_id": "INC-001", "service": "checkout-api", "query": "database"},
                        "id": "call-logs",
                        "type": "tool_call",
                    },
                    {
                        "name": "get_metrics",
                        "args": {"incident_id": "INC-001", "service": "checkout-api"},
                        "id": "call-metrics",
                        "type": "tool_call",
                    },
                    {
                        "name": "get_recent_deployments",
                        "args": {"service": "checkout-api", "before": "2026-10-17T10:02:00Z"},
                        "id": "call-deployments",
                        "type": "tool_call",
                    },
                    {
                        "name": "search_runbooks",
                        "args": {"query": "database connection timeout"},
                        "id": "call-runbooks",
                        "type": "tool_call",
                    },
                ],
            )

        return AIMessage(content="The deployment reduced the database connection pool and caused connection exhaustion.")


class FakeReportModel:
    def invoke(self, messages):
        return IncidentReport(
            incident_id="INC-001",
            affected_service="checkout-api",
            root_cause="Database connection pool exhaustion caused by reducing DB_POOL_MAX_SIZE.",
            confidence=0.95,
            evidence=["log-001", "metric-001", "deployment-001"],
            recommended_actions=["Roll back the database pool configuration."],
        )


class FakeModel:
    def __init__(self):
        self.investigation_model = FakeInvestigationModel()

    def bind_tools(self, tools):
        return self.investigation_model

    def with_structured_output(self, schema, method="json_schema"):
        return FakeReportModel()


def test_incident_graph_collects_evidence_and_generates_report():
    graph = build_incident_graph(model=FakeModel())
    initial_state = {
        "messages": [],
        "incident_id": "INC-001",
        "incident": {},
        "collected_evidence": [],
        "report": None,
        "tool_call_count": 0,
        "errors": [],
    }

    result = graph.invoke(initial_state, config={"recursion_limit": 30})
    evidence_ids = {evidence.evidence_id for evidence in result["collected_evidence"]}

    assert result["report"].incident_id == "INC-001"
    assert result["report"].affected_service == "checkout-api"
    assert result["tool_call_count"] == 4
    assert {"log-001", "metric-001", "deployment-001"}.issubset(evidence_ids)
