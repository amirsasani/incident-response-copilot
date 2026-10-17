from src.tools.log_search import search_logs
from src.tools.metric_search import get_metrics
from src.tools.deployment_search import get_recent_deployments
from src.tools.runbook_search import search_runbooks


def test_search_logs_finds_database_errors():
    results = search_logs.invoke(
        {
            "incident_id": "INC-001",
            "service": "checkout-api",
            "query": "database",
        }
    )

    assert {
        result["evidence_id"]
        for result in results
    } == {"log-001", "log-003"}


def test_search_logs_filters_by_service():
    results = search_logs.invoke(
        {
            "incident_id": "INC-001",
            "service": "payment-api",
        }
    )

    assert len(results) == 1
    assert results[0]["evidence_id"] == "log-004"

def test_get_metrics_finds_pool_utilization():
    results = get_metrics.invoke({
        "incident_id": "INC-001",
        "service": "checkout-api",
        "metric_name": "pool_utilization",
    })

    assert len(results) == 1
    assert results[0]["evidence_id"] == "metric-001"
    assert results[0]["value"] == 100


def test_get_metrics_filters_by_service():
    results = get_metrics.invoke({
        "incident_id": "INC-001",
        "service": "checkout-api",
    })

    assert len(results) == 3

def test_get_recent_deployments_finds_checkout_deployment():
    results = get_recent_deployments.invoke({
        "service": "checkout-api",
        "before": "2026-10-17T10:02:00Z",
    })

    assert len(results) == 1
    assert results[0]["evidence_id"] == "deployment-001"
    assert results[0]["version"] == "1.8.0"


def test_get_recent_deployments_respects_before_timestamp():
    results = get_recent_deployments.invoke({
        "service": "checkout-api",
        "before": "2026-10-17T09:00:00Z",
    })

    assert results == []

def test_search_runbooks_finds_database_runbook():
    results = search_runbooks.invoke({
        "query": "database connection timeout",
    })

    assert len(results) == 1
    assert results[0]["evidence_id"] == "runbook-db-001"
    assert results[0]["title"] == "Database connection errors"


def test_search_runbooks_returns_empty_for_unrelated_query():
    results = search_runbooks.invoke({
        "query": "kubernetes autoscaling",
    })

    assert results == []