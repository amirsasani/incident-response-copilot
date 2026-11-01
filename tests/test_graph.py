from langchain_core.messages import AIMessage

from src.agent.graph import build_incident_graph
import pytest

from src.agent.nodes import create_report_node
from src.agent.state import Evidence, IncidentReport


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


class FakeNoToolInvestigationModel:
    def invoke(self, messages):
        return AIMessage(content="No tool calls were selected.")


class FakeNoToolModel:
    def bind_tools(self, tools):
        return FakeNoToolInvestigationModel()

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


def test_incident_graph_falls_back_when_model_does_not_call_tools():
    graph = build_incident_graph(model=FakeNoToolModel())
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
    assert result["tool_call_count"] == 4
    assert {"log-001", "metric-001", "deployment-001", "runbook-db-001"}.issubset(evidence_ids)
    assert result["errors"] == []


class FakeRetryReportModel:
    def __init__(self, failures: int):
        self.failures = failures
        self.call_count = 0
        self.messages = []

    def invoke(self, messages):
        self.call_count += 1
        self.messages.append(messages)

        if self.call_count <= self.failures:
            raise ValueError("Malformed structured output.")

        return IncidentReport(incident_id="INC-001", affected_service="checkout-api", root_cause="Database pool exhaustion.", confidence=0.9, evidence=["metric-001"], recommended_actions=["Restore the pool size."])


class FakeRetryModel:
    def __init__(self, failures: int):
        self.report_model = FakeRetryReportModel(failures)

    def with_structured_output(self, schema, method="json_schema"):
        return self.report_model


def create_report_state() -> dict:
    return {
        "messages": [],
        "incident_id": "INC-001",
        "incident": {"incident_id": "INC-001", "service": "checkout-api"},
        "collected_evidence": [Evidence(evidence_id="metric-001", evidence_type="metric", source="checkout-api", summary="Pool utilization reached 100%.")],
        "report": None,
        "tool_call_count": 1,
        "errors": [],
    }


def test_report_generation_retries_once_after_parsing_failure():
    model = FakeRetryModel(failures=1)
    result = create_report_node(model)(create_report_state())

    assert result["report"].incident_id == "INC-001"
    assert model.report_model.call_count == 2
    assert result["errors"] == ["Report generation attempt 1 failed: ValueError: Malformed structured output."]
    assert "Return only one valid JSON object" in model.report_model.messages[1][-1].content


def test_report_generation_stops_after_second_failure():
    model = FakeRetryModel(failures=2)

    with pytest.raises(RuntimeError, match="failed after 2 attempts"):
        create_report_node(model)(create_report_state())

    assert model.report_model.call_count == 2
