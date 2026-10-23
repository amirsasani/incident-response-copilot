import argparse
import json
from pathlib import Path
from typing import Callable

from src.config import EXTERNAL_RCAEVAL_PATH, PROJECT_ROOT
from src.datasets.rcaeval import DEFAULT_REVISION, import_case


CASES_FILE = PROJECT_ROOT / "evaluation" / "rcaeval_cases.json"


def load_cases(path: Path) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(cases, list) or not cases:
        raise ValueError("RCAEval cases must contain a non-empty list.")

    required_fields = {"case", "incident_id", "expected_service", "expected_fault"}

    for case in cases:
        missing_fields = required_fields - set(case)

        if missing_fields:
            raise ValueError(f"RCAEval case is missing fields: {sorted(missing_fields)}")

    return cases


def import_cases(cases: list[dict], output_root: Path, revision: str, metric_limit: int, log_limit: int, trace_limit: int, importer: Callable = import_case) -> dict:
    imported = []
    failures = []

    for position, case in enumerate(cases, start=1):
        print(f"[{position}/{len(cases)}] Importing {case['case']}...", flush=True)

        try:
            result = importer(case["case"], output_root, revision, metric_limit, log_limit, trace_limit)

            if result["incident_id"] != case["incident_id"]:
                raise ValueError(f"Unexpected incident ID: {result['incident_id']}")

            labels = result["labels"]

            if labels["expected_service"] != case["expected_service"] or labels["expected_fault"] != case["expected_fault"]:
                raise ValueError("Imported labels do not match the evaluation manifest.")

            imported.append(result)
        except Exception as error:
            failures.append({"case": case["case"], "error": f"{type(error).__name__}: {error}"})

    return {"cases_requested": len(cases), "cases_imported": len(imported), "cases_failed": len(failures), "failures": failures, "imports": imported}


def main():
    parser = argparse.ArgumentParser(description="Download and normalize the balanced RCAEval evaluation set.")
    parser.add_argument("--cases_file", type=Path, default=CASES_FILE)
    parser.add_argument("--output_root", type=Path, default=EXTERNAL_RCAEVAL_PATH)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--metric_limit", type=int, default=100)
    parser.add_argument("--log_limit", type=int, default=500)
    parser.add_argument("--trace_limit", type=int, default=500)
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1.")

    cases = load_cases(args.cases_file)
    cases = cases[:args.limit] if args.limit else cases
    result = import_cases(cases, args.output_root, args.revision, args.metric_limit, args.log_limit, args.trace_limit)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
