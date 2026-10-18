from langchain_core.messages import AIMessage

from src.agent.state import Evidence, IncidentReport
from scripts.evaluate_agent import evaluate, root_cause_keyword_recall, root_cause_token_f1


class FakeGraph:
    def stream(self, initial_state, config, stream_mode):
        investigation_state = {
            **initial_state,
            "messages": [AIMessage(content="The database pool was exhausted.")],
            "collected_evidence": [
                Evidence(evidence_id="log-test", evidence_type="log", source="checkout-api", summary="Database connection timed out."),
                Evidence(evidence_id="metric-test", evidence_type="metric", source="checkout-api", summary="Pool utilization reached 100 percent."),
                Evidence(evidence_id="deployment-test", evidence_type="deployment", source="checkout-api", summary="Pool size was reduced."),
            ],
            "tool_call_count": 3,
        }
        yield investigation_state
        yield {
            **investigation_state,
            "report": IncidentReport(
                incident_id="INC-TEST",
                affected_service="checkout-api",
                root_cause="Database connection pool exhaustion after reducing the configured pool size.",
                confidence=0.9,
                evidence=["log-test", "metric-test", "deployment-test"],
                recommended_actions=["Restore the previous pool size."],
            ),
        }


def test_root_cause_token_f1_detects_overlap():
    score = root_cause_token_f1(
        "Database connection pool exhaustion caused by reducing the pool size",
        "Database connection pool exhaustion after reducing the configured pool size",
    )

    assert score > 0.5


def test_root_cause_keyword_recall_matches_phrases_and_normalizes_underscores():
    score = root_cause_keyword_recall(
        ["database", "connection pool", "db_pool_max_size"],
        "Database connection pool exhaustion followed a DB POOL MAX SIZE reduction.",
    )

    assert score == 1.0


def test_evaluate_calculates_agent_metrics():
    cases = [
        {
            "incident_id": "INC-TEST",
            "expected_service": "checkout-api",
            "expected_root_cause": "Database connection pool exhaustion caused by reducing the configured pool size",
            "root_cause_keywords": ["database", "connection pool", "db_pool_max_size"],
            "required_evidence": ["log-test", "metric-test", "deployment-test"],
        }
    ]

    results = evaluate(cases, FakeGraph(), root_cause_threshold=2 / 3, timeout_seconds=0)

    assert results["completion_rate"] == 1.0
    assert results["service_accuracy"] == 1.0
    assert results["root_cause_match_rate"] == 1.0
    assert results["average_root_cause_keyword_recall"] == 0.667
    assert results["required_evidence_recall"] == 1.0
    assert results["invalid_citation_rate"] == 0.0
    assert results["average_tool_calls"] == 3.0
    assert results["average_investigation_seconds"] >= 0.0
    assert results["average_report_generation_seconds"] >= 0.0
