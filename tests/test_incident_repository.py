import pytest

from src.incidents.repository import load_incident


def test_load_incident_returns_incident_data():
    incident = load_incident("INC-001")

    assert incident["incident_id"] == "INC-001"
    assert incident["service"] == "checkout-api"


def test_load_memory_leak_incident():
    incident = load_incident("INC-002")

    assert incident["service"] == "recommendation-api"
    assert incident["severity"] == "high"


def test_load_incident_rejects_invalid_id():
    with pytest.raises(ValueError, match="Invalid incident ID"):
        load_incident("../INC-001")


def test_load_incident_rejects_unknown_incident():
    with pytest.raises(FileNotFoundError, match="Incident does not exist"):
        load_incident("INC-999")
