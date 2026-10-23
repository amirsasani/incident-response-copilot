import json

import pandas as pd

import src.incidents.storage as storage
from src.datasets.rcaeval import incident_id_for_case, normalize_case, normalize_logs, normalize_metrics, normalize_traces
from src.incidents.repository import load_incident
from src.tools.trace_search import search_traces


INJECT_TIME = 1_700_000_000


def create_metrics_frame():
    return pd.DataFrame({
        "time": [INJECT_TIME - 2, INJECT_TIME - 1, INJECT_TIME, INJECT_TIME + 1],
        "adservice_cpu": [10.0, 10.0, 90.0, 100.0],
        "frontend_latency": [20.0, 21.0, 22.0, 21.0],
    })


def create_logs_frame():
    return pd.DataFrame({
        "timestamp": [INJECT_TIME - 1, INJECT_TIME + 1, INJECT_TIME + 2],
        "container_name": ["frontend", "adservice", "adservice"],
        "message": ["request completed", "fatal CPU throttling error", "fatal CPU throttling error"],
    })


def create_traces_frame():
    return pd.DataFrame({
        "time": [INJECT_TIME - 1, INJECT_TIME + 1],
        "traceID": ["trace-ok", "trace-error"],
        "spanID": ["span-ok", "span-error"],
        "parentSpanID": ["", "parent-error"],
        "serviceName": ["frontend", "adservice"],
        "operationName": ["GET /", "GetAds"],
        "duration": [10.0, 900.0],
        "statusCode": [0, 2],
    })


def create_metadata():
    return {
        "case": "re2ob_adservice_cpu_1",
        "dataset": "RE2-OB",
        "system_name": "Online Boutique",
        "root_cause_service": "adservice",
        "fault": "cpu",
        "fault_description": "CPU stress",
        "inject_time": INJECT_TIME,
    }


def test_normalizers_prioritize_anomalous_and_error_evidence():
    metrics = normalize_metrics(create_metrics_frame(), INJECT_TIME)
    logs = normalize_logs(create_logs_frame(), INJECT_TIME)
    traces = normalize_traces(create_traces_frame(), INJECT_TIME)

    assert metrics[0]["service"] == "adservice"
    assert metrics[0]["metric"] == "cpu"
    assert logs[0]["service"] == "adservice"
    assert len(logs) == 2
    assert traces[0]["trace_id"] == "trace-error"
    assert traces[0]["is_error"] is True


def test_normalize_case_creates_agent_ready_files(tmp_path, monkeypatch):
    result = normalize_case(create_metadata(), create_metrics_frame(), create_logs_frame(), create_traces_frame(), output_root=tmp_path)
    incident_id = incident_id_for_case("re2ob_adservice_cpu_1")
    case_directory = tmp_path / incident_id
    monkeypatch.setattr(storage, "EXTERNAL_RCAEVAL_PATH", tmp_path)

    incident = load_incident(incident_id)
    traces = search_traces.invoke({"incident_id": incident_id, "service": "adservice", "errors_only": True})
    labels = json.loads((case_directory / "labels.json").read_text(encoding="utf-8"))

    assert result["incident_id"] == incident_id
    assert incident["available_evidence"] == ["logs", "metrics", "traces"]
    assert traces[0]["trace_id"] == "trace-error"
    assert labels["expected_service"] == "adservice"
    assert labels["expected_fault"] == "cpu"
