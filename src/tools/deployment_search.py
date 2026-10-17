import json
from datetime import datetime

from langchain_core.tools import tool

from src.config import DEPLOYMENTS_FILE


def parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Invalid timestamp: {value}") from error


def load_deployments() -> list[dict]:
    if not DEPLOYMENTS_FILE.exists():
        raise FileNotFoundError(f"Deployments file does not exist: {DEPLOYMENTS_FILE}")

    with DEPLOYMENTS_FILE.open("r", encoding="utf-8") as file:
        deployments = json.load(file)

    if not isinstance(deployments, list):
        raise ValueError("Deployments file must contain a list.")

    return deployments


@tool
def get_recent_deployments(service: str, before: str | None = None, limit: int = 5) -> list[dict]:
    """Return recent deployments for a service, optionally before a timestamp."""

    if not service.strip():
        raise ValueError("service cannot be empty.")

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    deployments = load_deployments()
    before_timestamp = parse_timestamp(before) if before else None
    results = []

    for deployment in deployments:
        if deployment.get("service") != service:
            continue

        deployed_at = parse_timestamp(deployment["deployed_at"])

        if before_timestamp and deployed_at > before_timestamp:
            continue

        results.append(deployment)

    results.sort(key=lambda deployment: parse_timestamp(deployment["deployed_at"]), reverse=True)

    return results[:limit]