import argparse
import json
from pathlib import Path

from src.config import EXTERNAL_RCAEVAL_PATH
from src.datasets.rcaeval import DEFAULT_CASE, DEFAULT_REVISION, import_case


def main():
    parser = argparse.ArgumentParser(description="Download and normalize one RCAEval RE2 case.")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--output_root", type=Path, default=EXTERNAL_RCAEVAL_PATH)
    parser.add_argument("--metric_limit", type=int, default=100)
    parser.add_argument("--log_limit", type=int, default=500)
    parser.add_argument("--trace_limit", type=int, default=500)
    args = parser.parse_args()
    result = import_case(args.case, args.output_root, args.revision, args.metric_limit, args.log_limit, args.trace_limit)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
