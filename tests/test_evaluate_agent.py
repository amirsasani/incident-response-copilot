from src.agent.state import Evidence, IncidentReport
from scripts.evaluate_agent import evaluate, root_cause_token_f1


class FakeGraph:
    def invoke(self, initial_state, config):
        return {
            "report": IncidentReport(
                incident_id="INC-TEST",
                affected_service="checkout-api",
                root_cause="Database connection pool exhaustion after reducing the configured pool size.",
                confidence=0.9,
                evidence=["log-test", "metric-test", "deployment-test"],
                recommended_actions=["Restore the previous pool size."],
            ),
            "collected_evidence": [
                Evidence(evidence_id="log-test", evidence_type="log", source="checkout-api", summary="Database connection timed out."),
                Evidence(evidence_id="metric-test", evidence_type="metric", source="checkout-api", summary="Pool utilization reached 100 percent."),
                Evidence(evidence_id="deployment-test", evidence_type="deployment", source="checkout-api", summary="Pool size was reduced."),
            ],
            "tool_call_count": 3,
        }


def test_root_cause_token_f1_detects_overlap():
    score = root_cause_token_f1(
        "Database connection pool exhaustion caused by reducing the pool size",
        "Database connection pool exhaustion after reducing the configured pool size",
    )

    assert score > 0.5


def test_evaluate_calculates_agent_metrics():
    cases = [
        {
            "incident_id": "INC-TEST",
            "expected_service": "checkout-api",
            "expected_root_cause": "Database connection pool exhaustion caused by reducing the configured pool size",
            "required_evidence": ["log-test", "metric-test", "deployment-test"],
        }
    ]

    results = evaluate(cases, FakeGraph(), root_cause_threshold=0.3, timeout_seconds=0)

    assert results["completion_rate"] == 1.0
    assert results["service_accuracy"] == 1.0
    assert results["root_cause_match_rate"] == 1.0
    assert results["required_evidence_recall"] == 1.0
    assert results["invalid_citation_rate"] == 0.0
    assert results["average_tool_calls"] == 3.0
