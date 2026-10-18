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


def test_search_logs_finds_memory_pressure():
    results = search_logs.invoke({
        "incident_id": "INC-002",
        "service": "recommendation-api",
        "query": "heap",
    })

    assert len(results) == 1
    assert results[0]["evidence_id"] == "log-005"


def test_search_logs_finds_reduced_consumer_count():
    results = search_logs.invoke({
        "incident_id": "INC-003",
        "service": "notification-worker",
        "query": "consumer",
    })

    assert len(results) == 1
    assert results[0]["evidence_id"] == "log-011"


def test_search_logs_finds_dependency_dns_failure():
    results = search_logs.invoke({
        "incident_id": "INC-004",
        "service": "payment-api",
        "query": "DNS resolution",
    })

    assert len(results) == 1
    assert results[0]["evidence_id"] == "log-013"

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


def test_get_metrics_finds_heap_utilization():
    results = get_metrics.invoke({
        "incident_id": "INC-002",
        "service": "recommendation-api",
        "metric_name": "heap_utilization",
    })

    assert len(results) == 1
    assert results[0]["evidence_id"] == "metric-005"
    assert results[0]["value"] == 96


def test_get_metrics_finds_queue_depth():
    results = get_metrics.invoke({
        "incident_id": "INC-003",
        "service": "notification-worker",
        "metric_name": "queue_depth",
    })

    assert len(results) == 1
    assert results[0]["evidence_id"] == "metric-008"
    assert results[0]["value"] == 18500


def test_get_metrics_finds_provider_error_rate():
    results = get_metrics.invoke({
        "incident_id": "INC-004",
        "service": "payment-api",
        "metric_name": "provider_error_rate",
    })

    assert len(results) == 1
    assert results[0]["evidence_id"] == "metric-012"
    assert results[0]["value"] == 98

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


def test_get_recent_deployments_finds_cache_change():
    results = get_recent_deployments.invoke({
        "service": "recommendation-api",
        "before": "2026-10-18T14:20:00Z",
    })

    assert len(results) == 2
    assert results[0]["evidence_id"] == "deployment-003"
    assert results[0]["version"] == "3.2.0"


def test_get_recent_deployments_finds_concurrency_change():
    results = get_recent_deployments.invoke({
        "service": "notification-worker",
        "before": "2026-10-18T16:10:00Z",
    })

    assert len(results) == 2
    assert results[0]["evidence_id"] == "deployment-005"
    assert results[0]["version"] == "2.7.0"


def test_get_recent_deployments_finds_provider_endpoint_change():
    results = get_recent_deployments.invoke({
        "service": "payment-api",
        "before": "2026-10-18T17:42:00Z",
    })

    assert len(results) == 2
    assert results[0]["evidence_id"] == "deployment-007"
    assert results[0]["version"] == "2.5.0"

def test_search_runbooks_finds_database_runbook():
    results = search_runbooks.invoke({
        "query": "database connection timeout",
    })

    assert results[0]["evidence_id"] == "runbook-db-001"
    assert results[0]["title"] == "Database connection errors"


def test_search_runbooks_returns_empty_for_unrelated_query():
    results = search_runbooks.invoke({
        "query": "kubernetes autoscaling",
    })

    assert results == []


def test_search_runbooks_finds_memory_leak_runbook():
    results = search_runbooks.invoke({
        "query": "memory leak heap garbage collection",
    })

    assert results[0]["evidence_id"] == "runbook-memory-001"
    assert results[0]["title"] == "Application memory leaks"


def test_search_runbooks_finds_queue_backlog_runbook():
    results = search_runbooks.invoke({
        "query": "notification queue backlog consumer throughput",
    })

    assert results[0]["evidence_id"] == "runbook-queue-001"
    assert results[0]["title"] == "Message queue backlogs"


def test_search_runbooks_finds_dependency_outage_runbook():
    results = search_runbooks.invoke({
        "query": "upstream dependency DNS circuit breaker",
    })

    assert results[0]["evidence_id"] == "runbook-dependency-001"
    assert results[0]["title"] == "Upstream dependency outages"
