import argparse
import json
import re
import signal
import time
from contextlib import contextmanager
from pathlib import Path

from src.agent.graph import build_incident_graph
from src.config import OLLAMA_MODEL, PROJECT_ROOT


CASES_FILE = PROJECT_ROOT / "evaluation" / "incident_cases.json"
OUTPUT_FILE = PROJECT_ROOT / "evaluation" / "results.json"
TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "was",
}


class EvaluationTimeoutError(TimeoutError):
    pass


def load_cases(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation cases must contain a non-empty list.")

    required_fields = {"incident_id", "expected_service", "expected_root_cause", "required_evidence"}

    for case in cases:
        missing_fields = required_fields - set(case)

        if missing_fields:
            raise ValueError(f"Evaluation case is missing fields: {sorted(missing_fields)}")

        if not isinstance(case["required_evidence"], list) or not case["required_evidence"]:
            raise ValueError(f"Evaluation case {case['incident_id']} must define required evidence.")

    return cases


def tokenize(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.casefold())) - STOPWORDS


def root_cause_token_f1(expected: str, actual: str) -> float:
    expected_tokens = tokenize(expected)
    actual_tokens = tokenize(actual)

    if not expected_tokens or not actual_tokens:
        return 0.0

    overlap = len(expected_tokens & actual_tokens)
    precision = overlap / len(actual_tokens)
    recall = overlap / len(expected_tokens)

    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall)


def create_initial_state(incident_id: str) -> dict:
    return {
        "messages": [],
        "incident_id": incident_id,
        "incident": {},
        "collected_evidence": [],
        "report": None,
        "tool_call_count": 0,
        "errors": [],
    }


def handle_timeout(signum, frame):
    raise EvaluationTimeoutError("Investigation exceeded its time limit.")


@contextmanager
def time_limit(seconds: int):
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        yield
        return

    previous_handler = signal.signal(signal.SIGALRM, handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)

    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def evaluate_case(graph, case: dict, root_cause_threshold: float, timeout_seconds: int) -> dict:
    incident_id = case["incident_id"]
    started_at = time.perf_counter()

    try:
        with time_limit(timeout_seconds):
            state = graph.invoke(create_initial_state(incident_id), config={"recursion_limit": 30})

        report = state["report"]
        collected_evidence_ids = {evidence.evidence_id for evidence in state["collected_evidence"]}
        cited_evidence_ids = set(report.evidence)
        required_evidence_ids = set(case["required_evidence"])
        invalid_evidence_ids = cited_evidence_ids - collected_evidence_ids
        found_required_evidence = cited_evidence_ids & required_evidence_ids
        evidence_recall = len(found_required_evidence) / len(required_evidence_ids)
        root_cause_f1 = root_cause_token_f1(case["expected_root_cause"], report.root_cause)

        return {
            "incident_id": incident_id,
            "status": "completed",
            "expected_service": case["expected_service"],
            "actual_service": report.affected_service,
            "service_correct": report.affected_service == case["expected_service"],
            "expected_root_cause": case["expected_root_cause"],
            "actual_root_cause": report.root_cause,
            "root_cause_token_f1": round(root_cause_f1, 3),
            "root_cause_match": root_cause_f1 >= root_cause_threshold,
            "required_evidence": sorted(required_evidence_ids),
            "cited_evidence": sorted(cited_evidence_ids),
            "missing_required_evidence": sorted(required_evidence_ids - cited_evidence_ids),
            "invalid_evidence": sorted(invalid_evidence_ids),
            "required_evidence_recall": round(evidence_recall, 3),
            "tool_call_count": state["tool_call_count"],
            "latency_seconds": round(time.perf_counter() - started_at, 3),
            "error": None,
        }
    except Exception as error:
        return {
            "incident_id": incident_id,
            "status": "failed",
            "expected_service": case["expected_service"],
            "actual_service": None,
            "service_correct": False,
            "expected_root_cause": case["expected_root_cause"],
            "actual_root_cause": None,
            "root_cause_token_f1": 0.0,
            "root_cause_match": False,
            "required_evidence": sorted(case["required_evidence"]),
            "cited_evidence": [],
            "missing_required_evidence": sorted(case["required_evidence"]),
            "invalid_evidence": [],
            "required_evidence_recall": 0.0,
            "tool_call_count": 0,
            "latency_seconds": round(time.perf_counter() - started_at, 3),
            "error": f"{type(error).__name__}: {error}",
        }


def summarize_results(case_results: list[dict], root_cause_threshold: float) -> dict:
    case_count = len(case_results)
    completed = [result for result in case_results if result["status"] == "completed"]
    total_citations = sum(len(result["cited_evidence"]) for result in completed)
    invalid_citations = sum(len(result["invalid_evidence"]) for result in completed)

    return {
        "method": "LangGraph tools + Ollama structured report",
        "model": OLLAMA_MODEL,
        "incidents_evaluated": case_count,
        "incidents_completed": len(completed),
        "completion_rate": round(len(completed) / case_count, 3),
        "service_accuracy": round(sum(result["service_correct"] for result in case_results) / case_count, 3),
        "root_cause_match_threshold": root_cause_threshold,
        "root_cause_match_rate": round(sum(result["root_cause_match"] for result in case_results) / case_count, 3),
        "average_root_cause_token_f1": round(sum(result["root_cause_token_f1"] for result in case_results) / case_count, 3),
        "required_evidence_recall": round(sum(result["required_evidence_recall"] for result in case_results) / case_count, 3),
        "invalid_citation_rate": round(invalid_citations / total_citations, 3) if total_citations else 0.0,
        "average_tool_calls": round(sum(result["tool_call_count"] for result in case_results) / case_count, 3),
        "average_latency_seconds": round(sum(result["latency_seconds"] for result in case_results) / case_count, 3),
        "failures": [result["incident_id"] for result in case_results if result["status"] == "failed"],
        "cases": case_results,
    }


def evaluate(cases: list[dict], graph, root_cause_threshold: float, timeout_seconds: int) -> dict:
    case_results = []

    for position, case in enumerate(cases, start=1):
        incident_id = case["incident_id"]
        print(f"[{position}/{len(cases)}] Evaluating {incident_id}...", flush=True)
        result = evaluate_case(graph, case, root_cause_threshold, timeout_seconds)
        case_results.append(result)
        print(f"{incident_id}: {result['status']} in {result['latency_seconds']:.3f}s", flush=True)

    return summarize_results(case_results, root_cause_threshold)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases_file", type=Path, default=CASES_FILE)
    parser.add_argument("--output_file", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--incident_id", action="append")
    parser.add_argument("--root_cause_threshold", type=float, default=0.3)
    parser.add_argument("--timeout_seconds", type=int, default=240)
    args = parser.parse_args()

    if not 0 <= args.root_cause_threshold <= 1:
        parser.error("--root_cause_threshold must be between 0 and 1.")

    if args.timeout_seconds < 0:
        parser.error("--timeout_seconds cannot be negative.")

    cases = load_cases(args.cases_file)

    if args.incident_id:
        selected_ids = set(args.incident_id)
        cases = [case for case in cases if case["incident_id"] in selected_ids]
        missing_ids = selected_ids - {case["incident_id"] for case in cases}

        if missing_ids:
            parser.error(f"Unknown incident IDs: {sorted(missing_ids)}")

    graph = build_incident_graph()
    results = evaluate(cases, graph, args.root_cause_threshold, args.timeout_seconds)

    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {key: value for key, value in results.items() if key != "cases"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Detailed results written to {args.output_file}")


if __name__ == "__main__":
    main()
