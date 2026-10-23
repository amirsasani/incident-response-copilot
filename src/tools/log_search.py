import json

from langchain_core.tools import tool

from src.incidents.storage import get_incident_data_file


def load_logs(incident_id: str) -> list[dict]:
    log_file = get_incident_data_file(incident_id, "logs")

    if not log_file.exists():
        raise FileNotFoundError(f"No logs found for incident {incident_id}.")

    logs = []

    with log_file.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number} of {log_file}.") from error

    return logs


@tool
def search_logs(
    incident_id: str,
    service: str | None = None,
    query: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search incident logs by service and message content."""

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    logs = load_logs(incident_id)
    normalized_query = query.casefold().strip() if query else None

    results = []

    for log in logs:
        if service and log.get("service") != service:
            continue

        searchable_text = " ".join(
            str(log.get(field, "")) for field in ("level", "message", "trace_id")
        ).casefold()

        if normalized_query and normalized_query not in searchable_text:
            continue

        results.append(log)

    return results[:limit]
