import json

from langchain_core.tools import tool

from src.incidents.storage import get_incident_data_file


def load_traces(incident_id: str) -> list[dict]:
    trace_file = get_incident_data_file(incident_id, "traces")

    if not trace_file.exists():
        raise FileNotFoundError(f"No traces found for incident {incident_id}.")

    traces = []

    with trace_file.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number} of {trace_file}.") from error

    return traces


@tool
def search_traces(incident_id: str, service: str | None = None, operation: str | None = None, errors_only: bool = False, limit: int = 20) -> list[dict]:
    """Search distributed trace spans by service, operation and error status."""

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    traces = load_traces(incident_id)
    normalized_operation = operation.casefold().strip() if operation else None
    results = []

    for trace in traces:
        if service and trace.get("service") != service:
            continue

        if normalized_operation and normalized_operation not in str(trace.get("operation", "")).casefold():
            continue

        if errors_only and not trace.get("is_error", False):
            continue

        results.append(trace)

    return results[:limit]
