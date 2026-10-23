import argparse
import json
import re
import time
from pathlib import Path

from src.agent.graph import build_incident_graph
from src.config import OLLAMA_MODEL, PROJECT_ROOT
from src.incidents.storage import get_incident_data_file
from scripts.evaluate_agent import create_initial_state, time_limit
from scripts.import_rcaeval_batch import CASES_FILE, load_cases


OUTPUT_FILE = PROJECT_ROOT / "evaluation" / "rcaeval_results.json"
FAULT_TERMS = {
    "cpu": ("cpu", "processor", "compute"),
    "delay": ("delay", "latency", "slow"),
    "disk": ("disk", "storage", "disk i/o", "disk io"),
    "loss": ("packet loss", "network loss", "dropped packet", "packet drop"),
    "mem": ("memory", "out of memory", "oom"),
    "socket": ("socket", "connection exhaustion", "connection failure"),
}


def normalize_service(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def fault_matches(expected_fault: str, root_cause: str) -> bool:
    normalized_root_cause = root_cause.casefold()
    terms = FAULT_TERMS.get(expected_fault)

    if not terms:
        raise ValueError(f"Unsupported RCAEval fault type: {expected_fault}")

    return any(term in normalized_root_cause for term in terms)


def validate_imported_labels(case: dict) -> dict:
    labels_file = get_incident_data_file(case["incident_id"], "labels")

    if not labels_file.exists():
        raise FileNotFoundError(f"RCAEval case is not imported: {case['case']}. Run python -m scripts.import_rcaeval_batch first.")

    labels = json.loads(labels_file.read_text(encoding="utf-8"))

    if labels["source_case"] != case["case"] or labels["expected_service"] != case["expected_service"] or labels["expected_fault"] != case["expected_fault"]:
        raise ValueError(f"Imported labels do not match the manifest for {case['case']}.")

    return labels


def evaluate_case(graph, case: dict, timeout_seconds: int) -> dict:
    started_at = time.perf_counter()

    try:
        validate_imported_labels(case)

        with time_limit(timeout_seconds):
            state = graph.invoke(create_initial_state(case["incident_id"]), config={"recursion_limit": 30})

        report = state["report"]

        if report is None:
            raise RuntimeError("The graph completed without generating a report.")

        collected_evidence_ids = {evidence.evidence_id for evidence in state["collected_evidence"]}
        cited_evidence_ids = set(report.evidence)
        invalid_evidence_ids = cited_evidence_ids - collected_evidence_ids
        service_correct = normalize_service(report.affected_service) == normalize_service(case["expected_service"])
        fault_correct = fault_matches(case["expected_fault"], report.root_cause)

        return {
            "case": case["case"],
            "incident_id": case["incident_id"],
            "status": "completed",
            "expected_service": case["expected_service"],
            "actual_service": report.affected_service,
            "service_correct": service_correct,
            "expected_fault": case["expected_fault"],
            "actual_root_cause": report.root_cause,
            "fault_correct": fault_correct,
            "joint_correct": service_correct and fault_correct,
            "cited_evidence": sorted(cited_evidence_ids),
            "invalid_evidence": sorted(invalid_evidence_ids),
            "evidence_valid": not invalid_evidence_ids,
            "tool_call_count": state["tool_call_count"],
            "latency_seconds": round(time.perf_counter() - started_at, 3),
            "error": None,
        }
    except Exception as error:
        return {
            "case": case["case"],
            "incident_id": case["incident_id"],
            "status": "failed",
            "expected_service": case["expected_service"],
            "actual_service": None,
            "service_correct": False,
            "expected_fault": case["expected_fault"],
            "actual_root_cause": None,
            "fault_correct": False,
            "joint_correct": False,
            "cited_evidence": [],
            "invalid_evidence": [],
            "evidence_valid": False,
            "tool_call_count": 0,
            "latency_seconds": round(time.perf_counter() - started_at, 3),
            "error": f"{type(error).__name__}: {error}",
        }


def summarize_results(case_results: list[dict]) -> dict:
    case_count = len(case_results)
    completed = [result for result in case_results if result["status"] == "completed"]

    return {
        "method": "LangGraph tools + Ollama structured report",
        "model": OLLAMA_MODEL,
        "dataset": "RCAEval RE2-OB",
        "cases_evaluated": case_count,
        "cases_completed": len(completed),
        "completion_rate": round(len(completed) / case_count, 3),
        "service_accuracy": round(sum(result["service_correct"] for result in case_results) / case_count, 3),
        "fault_accuracy": round(sum(result["fault_correct"] for result in case_results) / case_count, 3),
        "joint_accuracy": round(sum(result["joint_correct"] for result in case_results) / case_count, 3),
        "valid_evidence_rate": round(sum(result["evidence_valid"] for result in case_results) / case_count, 3),
        "average_tool_calls": round(sum(result["tool_call_count"] for result in case_results) / case_count, 3),
        "average_latency_seconds": round(sum(result["latency_seconds"] for result in case_results) / case_count, 3),
        "failures": [result["case"] for result in case_results if result["status"] == "failed"],
        "cases": case_results,
    }


def evaluate(cases: list[dict], graph, timeout_seconds: int) -> dict:
    case_results = []

    for position, case in enumerate(cases, start=1):
        print(f"[{position}/{len(cases)}] Evaluating {case['case']}...", flush=True)
        result = evaluate_case(graph, case, timeout_seconds)
        case_results.append(result)
        print(f"{case['case']}: {result['status']} in {result['latency_seconds']:.3f}s", flush=True)

    return summarize_results(case_results)


def main():
    parser = argparse.ArgumentParser(description="Evaluate the agent on the balanced RCAEval RE2-OB set.")
    parser.add_argument("--cases_file", type=Path, default=CASES_FILE)
    parser.add_argument("--output_file", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--case", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout_seconds", type=int, default=180)
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1.")

    if args.timeout_seconds < 0:
        parser.error("--timeout_seconds cannot be negative.")

    cases = load_cases(args.cases_file)

    if args.case:
        selected_cases = set(args.case)
        cases = [case for case in cases if case["case"] in selected_cases]
        missing_cases = selected_cases - {case["case"] for case in cases}

        if missing_cases:
            parser.error(f"Unknown RCAEval cases: {sorted(missing_cases)}")

    cases = cases[:args.limit] if args.limit else cases
    results = evaluate(cases, build_incident_graph(), args.timeout_seconds)
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in results.items() if key != "cases"}, indent=2, ensure_ascii=False))
    print(f"Detailed results written to {args.output_file}")


if __name__ == "__main__":
    main()
