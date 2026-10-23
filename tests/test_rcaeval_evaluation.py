from collections import Counter

import pytest

import src.incidents.storage as storage
from scripts.evaluate_rcaeval import evaluate, fault_matches, normalize_service
from scripts.import_rcaeval_batch import CASES_FILE, import_cases, load_cases
from src.agent.state import Evidence, IncidentReport


class FakeGraph:
    def invoke(self, initial_state, config):
        return {
            "report": IncidentReport(
                incident_id=initial_state["incident_id"],
                affected_service="checkout-service",
                root_cause="Sustained CPU saturation in checkoutservice.",
                confidence=0.9,
                evidence=["rcaeval-metric-001"],
                recommended_actions=["Inspect CPU-intensive work."],
            ),
            "collected_evidence": [Evidence(evidence_id="rcaeval-metric-001", evidence_type="metric", source="checkoutservice", summary="CPU increased after injection.")],
            "tool_call_count": 3,
        }


def test_balanced_manifest_covers_every_fault_twice():
    cases = load_cases(CASES_FILE)
    fault_counts = Counter(case["expected_fault"] for case in cases)
    service_counts = Counter(case["expected_service"] for case in cases)

    assert len(cases) == 12
    assert set(fault_counts.values()) == {2}
    assert set(service_counts.values()) == {2, 3}
    assert len({case["incident_id"] for case in cases}) == 12


def test_batch_import_validates_imported_labels(tmp_path):
    case = load_cases(CASES_FILE)[0]

    def fake_importer(case_name, output_root, revision, metric_limit, log_limit, trace_limit):
        return {
            "incident_id": case["incident_id"],
            "case": case_name,
            "labels": {"expected_service": case["expected_service"], "expected_fault": case["expected_fault"]},
        }

    result = import_cases([case], tmp_path, "revision", 10, 10, 10, importer=fake_importer)

    assert result["cases_imported"] == 1
    assert result["cases_failed"] == 0


@pytest.mark.parametrize(
    ("fault", "root_cause"),
    [
        ("cpu", "CPU saturation"),
        ("delay", "Network latency increased"),
        ("disk", "Disk I/O saturation"),
        ("loss", "Network packet loss"),
        ("mem", "Out of memory failure"),
        ("socket", "Socket exhaustion"),
    ],
)
def test_fault_matches_supported_rcaeval_faults(fault, root_cause):
    assert fault_matches(fault, root_cause) is True


def test_external_evaluation_calculates_service_fault_and_evidence_metrics(tmp_path, monkeypatch):
    case = load_cases(CASES_FILE)[0]
    case_directory = tmp_path / case["incident_id"]
    case_directory.mkdir()
    (case_directory / "labels.json").write_text(
        '{"source_case":"re2ob_checkoutservice_cpu_1","expected_service":"checkoutservice","expected_fault":"cpu"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(storage, "EXTERNAL_RCAEVAL_PATH", tmp_path)

    results = evaluate([case], FakeGraph(), timeout_seconds=0)

    assert normalize_service("checkout-service") == "checkoutservice"
    assert results["completion_rate"] == 1.0
    assert results["service_accuracy"] == 1.0
    assert results["fault_accuracy"] == 1.0
    assert results["joint_accuracy"] == 1.0
    assert results["valid_evidence_rate"] == 1.0
