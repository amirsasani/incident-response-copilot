import json

from langchain_core.tools import tool

from src.incidents.storage import get_incident_data_file


def load_metrics(incident_id: str) -> list[dict]:
    metrics_file = get_incident_data_file(incident_id, "metrics")

    if not metrics_file.exists():
        raise FileNotFoundError(f"No metrics found for incident {incident_id}.")

    with metrics_file.open("r", encoding="utf-8") as file:
        metrics = json.load(file)

    if not isinstance(metrics, list):
        raise ValueError("Metrics file must contain a list.")

    return metrics


@tool
def get_metrics(incident_id: str, service: str | None = None, metric_name: str | None = None, limit: int = 20) -> list[dict]:
    """Retrieve incident metrics filtered by service and metric name."""

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    metrics = load_metrics(incident_id)
    normalized_metric_name = metric_name.casefold().strip() if metric_name else None
    results = []

    for metric in metrics:
        if service and metric.get("service") != service:
            continue

        current_metric_name = str(metric.get("metric", "")).casefold()

        if normalized_metric_name and normalized_metric_name not in current_metric_name:
            continue

        results.append(metric)

    return results[:limit]
