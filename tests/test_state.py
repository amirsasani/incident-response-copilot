import pytest
from pydantic import ValidationError

from src.agent.state import Evidence, IncidentReport


def test_incident_report_validates_confidence():
    with pytest.raises(ValidationError):
        IncidentReport(
            incident_id="INC-001",
            affected_service="checkout-api",
            root_cause="Database connection pool exhaustion",
            confidence=1.5,
            evidence=["log-001"],
            recommended_actions=["Restore the previous pool configuration."],
        )


def test_evidence_accepts_structured_metadata():
    evidence = Evidence(
        evidence_id="metric-001",
        evidence_type="metric",
        source="checkout-api",
        summary="Database pool utilization reached 100%.",
        metadata={"value": 100, "unit": "percent"},
    )

    assert evidence.metadata["value"] == 100