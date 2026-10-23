import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from huggingface_hub import hf_hub_download

from src.config import EXTERNAL_RCAEVAL_PATH


RCAEVAL_REPO_ID = "phamquiluan/RCAEval"
DEFAULT_REVISION = "afeacb11bcc94dadfd1c8f483ee4377b2b8b614e"
DEFAULT_CASE = "re2ob_checkoutservice_cpu_1"
CASE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]+$")


def incident_id_for_case(case_name: str) -> str:
    if not CASE_NAME_PATTERN.fullmatch(case_name):
        raise ValueError("Invalid RCAEval case name.")

    return f"RCAEVAL-{case_name.upper().replace('_', '-')}"


def python_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None

    if hasattr(value, "item"):
        value = value.item()

    if isinstance(value, float) and math.isnan(value):
        return None

    return value


def epoch_seconds(value: Any) -> float | None:
    value = python_value(value)

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.timestamp()

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        parsed = pd.to_datetime(value, utc=True, errors="coerce")
        return None if pd.isna(parsed) else parsed.timestamp()

    magnitude = abs(numeric_value)

    if magnitude >= 1e17:
        return numeric_value / 1e9

    if magnitude >= 1e14:
        return numeric_value / 1e6

    if magnitude >= 1e11:
        return numeric_value / 1e3

    return numeric_value


def iso_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def find_column(frame: pd.DataFrame, candidates: tuple[str, ...], required: bool = True) -> str | None:
    columns = {column.casefold(): column for column in frame.columns}

    for candidate in candidates:
        if candidate.casefold() in columns:
            return columns[candidate.casefold()]

    if required:
        raise ValueError(f"Dataset is missing one of these columns: {candidates}")

    return None


def split_metric_name(column: str) -> tuple[str, str]:
    if "_" not in column:
        return "unknown", column

    return tuple(column.split("_", 1))


def normalize_metrics(frame: pd.DataFrame, inject_time: int, limit: int = 100) -> list[dict]:
    if limit < 1:
        raise ValueError("Metric limit must be at least 1.")

    time_column = find_column(frame, ("time", "timestamp"))
    timestamps = frame[time_column].map(epoch_seconds)
    baseline_mask = timestamps < inject_time
    faulty_mask = timestamps >= inject_time
    metrics = []

    for column in frame.columns:
        if column == time_column:
            continue

        values = pd.to_numeric(frame[column], errors="coerce")
        baseline = values[baseline_mask].dropna()
        faulty = values[faulty_mask].dropna()

        if baseline.empty or faulty.empty:
            continue

        baseline_mean = float(baseline.mean())
        faulty_mean = float(faulty.mean())
        baseline_std = float(baseline.std(ddof=0))
        scale = baseline_std if baseline_std > 1e-9 else max(abs(baseline_mean) * 0.05, 1e-9)
        anomaly_score = min(abs(faulty_mean - baseline_mean) / scale, 1_000_000.0)
        change_percent = None if abs(baseline_mean) <= 1e-9 else ((faulty_mean - baseline_mean) / abs(baseline_mean)) * 100
        service, metric_name = split_metric_name(str(column))
        metrics.append({
            "timestamp": iso_timestamp(inject_time),
            "service": service,
            "metric": metric_name,
            "value": round(faulty_mean, 6),
            "baseline_value": round(baseline_mean, 6),
            "change_percent": round(change_percent, 3) if change_percent is not None else None,
            "anomaly_score": round(anomaly_score, 3),
            "source_metric": str(column),
        })

    metrics.sort(key=lambda metric: (-metric["anomaly_score"], metric["source_metric"]))

    for position, metric in enumerate(metrics[:limit], start=1):
        metric["evidence_id"] = f"rcaeval-metric-{position:03d}"

    return metrics[:limit]


def infer_log_level(message: str) -> str:
    normalized_message = message.casefold()

    if any(term in normalized_message for term in ("error", "exception", "failed", "failure", "fatal", "panic")):
        return "ERROR"

    if any(term in normalized_message for term in ("warn", "timeout", "slow")):
        return "WARN"

    return "INFO"


def normalize_logs(frame: pd.DataFrame, inject_time: int, limit: int = 500, window_seconds: int = 600) -> list[dict]:
    if limit < 1:
        raise ValueError("Log limit must be at least 1.")

    timestamp_column = find_column(frame, ("timestamp", "time"))
    service_column = find_column(frame, ("container_name", "service_name", "service"))
    message_column = find_column(frame, ("message", "log_message", "body"))
    trace_column = find_column(frame, ("trace_id", "traceid", "traceID"), required=False)
    candidates = []

    for row in frame.to_dict(orient="records"):
        timestamp = epoch_seconds(row.get(timestamp_column))

        if timestamp is None or abs(timestamp - inject_time) > window_seconds:
            continue

        message = str(python_value(row.get(message_column)) or "")
        service = str(python_value(row.get(service_column)) or "unknown")
        level = infer_log_level(message)
        candidates.append({
            "timestamp": iso_timestamp(timestamp),
            "service": service,
            "level": level,
            "message": message,
            "trace_id": str(python_value(row.get(trace_column)) or "") if trace_column else "",
            "_sort": ({"ERROR": 0, "WARN": 1, "INFO": 2}[level], abs(timestamp - inject_time)),
        })

    candidates.sort(key=lambda log: log["_sort"])
    logs = []
    seen = set()

    for candidate in candidates:
        duplicate_key = (candidate["service"], candidate["level"], candidate["message"])

        if duplicate_key in seen:
            continue

        seen.add(duplicate_key)
        candidate.pop("_sort")
        candidate["evidence_id"] = f"rcaeval-log-{len(logs) + 1:03d}"
        logs.append(candidate)

        if len(logs) == limit:
            break

    return logs


def trace_is_error(status_code: Any) -> bool:
    status_code = python_value(status_code)

    if status_code is None:
        return False

    normalized_status = str(status_code).casefold().strip()

    if normalized_status in {"", "0", "200", "ok", "unset", "status_code_ok", "status_code_unset"}:
        return False

    if "error" in normalized_status or "fail" in normalized_status:
        return True

    try:
        numeric_status = int(float(normalized_status))
    except ValueError:
        return False

    return numeric_status > 0 and not 200 <= numeric_status < 400


def normalize_traces(frame: pd.DataFrame, inject_time: int, limit: int = 500, window_seconds: int = 600) -> list[dict]:
    if limit < 1:
        raise ValueError("Trace limit must be at least 1.")

    timestamp_column = find_column(frame, ("startTimeMillis", "startTime", "timestamp", "time"))
    service_column = find_column(frame, ("serviceName", "service_name", "service"))
    trace_column = find_column(frame, ("traceID", "trace_id"))
    span_column = find_column(frame, ("spanID", "span_id"))
    parent_column = find_column(frame, ("parentSpanID", "parent_span_id"), required=False)
    operation_column = find_column(frame, ("operationName", "operation_name", "methodName", "name"), required=False)
    duration_column = find_column(frame, ("duration", "duration_ms"), required=False)
    status_column = find_column(frame, ("statusCode", "status_code", "http.status_code"), required=False)
    candidates = []

    for row in frame.to_dict(orient="records"):
        timestamp = epoch_seconds(row.get(timestamp_column))

        if timestamp is None or abs(timestamp - inject_time) > window_seconds:
            continue

        duration_value = python_value(row.get(duration_column)) if duration_column else None
        duration = float(duration_value) if duration_value is not None and not pd.isna(duration_value) else 0.0
        status_code = python_value(row.get(status_column)) if status_column else None
        is_error = trace_is_error(status_code)
        candidates.append({
            "timestamp": iso_timestamp(timestamp),
            "service": str(python_value(row.get(service_column)) or "unknown"),
            "operation": str(python_value(row.get(operation_column)) or "unknown") if operation_column else "unknown",
            "trace_id": str(python_value(row.get(trace_column)) or ""),
            "span_id": str(python_value(row.get(span_column)) or ""),
            "parent_span_id": str(python_value(row.get(parent_column)) or "") if parent_column else "",
            "duration": round(duration, 6),
            "status_code": status_code,
            "is_error": is_error,
            "_sort": (0 if is_error else 1, -duration, abs(timestamp - inject_time)),
        })

    candidates.sort(key=lambda trace: trace["_sort"])
    traces = []

    for candidate in candidates[:limit]:
        candidate.pop("_sort")
        candidate["evidence_id"] = f"rcaeval-trace-{len(traces) + 1:03d}"
        traces.append(candidate)

    return traces


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def write_json_lines(path: Path, values: list[dict]) -> None:
    content = "\n".join(json.dumps(value, ensure_ascii=False) for value in values)
    path.write_text(f"{content}\n" if content else "", encoding="utf-8")


def normalize_case(case_metadata: dict, metrics_frame: pd.DataFrame, logs_frame: pd.DataFrame, traces_frame: pd.DataFrame, output_root: Path = EXTERNAL_RCAEVAL_PATH, metric_limit: int = 100, log_limit: int = 500, trace_limit: int = 500) -> dict:
    case_name = str(case_metadata["case"])
    incident_id = incident_id_for_case(case_name)
    inject_time = int(case_metadata["inject_time"])
    case_directory = output_root / incident_id
    case_directory.mkdir(parents=True, exist_ok=True)
    metrics = normalize_metrics(metrics_frame, inject_time, metric_limit)
    logs = normalize_logs(logs_frame, inject_time, log_limit)
    traces = normalize_traces(traces_frame, inject_time, trace_limit)
    incident = {
        "incident_id": incident_id,
        "title": f"{case_metadata['system_name']} telemetry anomaly",
        "service": str(case_metadata["system_name"]).casefold().replace(" ", "-"),
        "severity": "high",
        "status": "investigating",
        "started_at": iso_timestamp(inject_time),
        "symptoms": ["A telemetry anomaly was detected after the benchmark fault-injection time.", "Use logs, metrics and traces to identify the affected service and fault type."],
        "available_evidence": ["logs", "metrics", "traces"],
        "source": {"dataset": "RCAEval", "case": case_name, "url": "https://huggingface.co/datasets/phamquiluan/RCAEval"},
    }
    labels = {
        "incident_id": incident_id,
        "source_case": case_name,
        "dataset": case_metadata["dataset"],
        "expected_service": case_metadata["root_cause_service"],
        "expected_fault": case_metadata["fault"],
        "fault_description": case_metadata["fault_description"],
        "inject_time": inject_time,
    }
    write_json(case_directory / "incident.json", incident)
    write_json(case_directory / "metrics.json", metrics)
    write_json_lines(case_directory / "logs.jsonl", logs)
    write_json_lines(case_directory / "traces.jsonl", traces)
    write_json(case_directory / "labels.json", labels)

    return {"incident_id": incident_id, "case": case_name, "output_directory": str(case_directory), "metrics": len(metrics), "logs": len(logs), "traces": len(traces), "labels": labels}


def download_case(case_name: str, revision: str = DEFAULT_REVISION) -> tuple[dict, dict[str, Path]]:
    incident_id_for_case(case_name)
    index_path = Path(hf_hub_download(repo_id=RCAEVAL_REPO_ID, filename="cases.parquet", repo_type="dataset", revision=revision))
    index = pd.read_parquet(index_path)
    matches = index[index["case"] == case_name]

    if matches.empty:
        raise ValueError(f"Unknown RCAEval case: {case_name}")

    metadata = {key: python_value(value) for key, value in matches.iloc[0].to_dict().items()}

    if metadata["suite"] != "RE2" or not metadata["has_logs"] or not metadata["has_traces"]:
        raise ValueError("Choose an RE2 case that includes both logs and traces.")

    filenames = ("metrics.parquet", "logs.parquet", "traces.parquet", "inject_time.txt")
    paths = {
        filename: Path(hf_hub_download(repo_id=RCAEVAL_REPO_ID, filename=f"{case_name}/{filename}", repo_type="dataset", revision=revision))
        for filename in filenames
    }
    metadata["inject_time"] = int(paths["inject_time.txt"].read_text(encoding="utf-8").strip())
    return metadata, paths


def import_case(case_name: str = DEFAULT_CASE, output_root: Path = EXTERNAL_RCAEVAL_PATH, revision: str = DEFAULT_REVISION, metric_limit: int = 100, log_limit: int = 500, trace_limit: int = 500) -> dict:
    metadata, paths = download_case(case_name, revision)
    metrics_frame = pd.read_parquet(paths["metrics.parquet"])
    logs_frame = pd.read_parquet(paths["logs.parquet"])
    traces_frame = pd.read_parquet(paths["traces.parquet"])
    return normalize_case(metadata, metrics_frame, logs_frame, traces_frame, output_root, metric_limit, log_limit, trace_limit)
