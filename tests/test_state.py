import pytest
from pydantic import ValidationError

from src.agent.state import Evidence, IncidentReport


@pytest.mark.parametrize("fault_type", ["cpu", "delay", "disk", "packet_loss", "memory", "socket", "unknown"])
def test_incident_report_accepts_supported_fault_types(fault_type):
    report = IncidentReport(incident_id="INC-001", affected_service="checkout-api", fault_type=fault_type, root_cause="Supported by evidence.", confidence=0.9, evidence=["metric-001"], recommended_actions=["Investigate the evidence."])

    assert report.fault_type == fault_type


def test_incident_report_rejects_unsupported_fault_type():
    with pytest.raises(ValidationError):
        IncidentReport(incident_id="INC-001", affected_service="checkout-api", fault_type="network", root_cause="Unsupported category.", confidence=0.9, evidence=["metric-001"], recommended_actions=["Investigate the evidence."])


def test_incident_report_validates_confidence():
    with pytest.raises(ValidationError):
        IncidentReport(
            incident_id="INC-001",
            affected_service="checkout-api",
            fault_type="unknown",
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
