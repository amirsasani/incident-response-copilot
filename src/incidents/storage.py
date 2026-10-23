import re
from pathlib import Path

from src.config import EXTERNAL_RCAEVAL_PATH, INCIDENTS_PATH, LOGS_PATH, METRICS_PATH, TRACES_PATH


INCIDENT_ID_PATTERN = re.compile(r"^(?:INC-\d+|RCAEVAL-[A-Z0-9-]+)$")
LEGACY_PATHS = {
    "incident": (INCIDENTS_PATH, ".json"),
    "logs": (LOGS_PATH, ".jsonl"),
    "metrics": (METRICS_PATH, ".json"),
    "traces": (TRACES_PATH, ".jsonl"),
}
EXTERNAL_FILENAMES = {
    "incident": "incident.json",
    "logs": "logs.jsonl",
    "metrics": "metrics.json",
    "traces": "traces.jsonl",
    "labels": "labels.json",
}


def validate_incident_id(incident_id: str) -> None:
    if not INCIDENT_ID_PATTERN.fullmatch(incident_id):
        raise ValueError("Invalid incident ID.")


def get_incident_data_file(incident_id: str, data_type: str) -> Path:
    validate_incident_id(incident_id)

    if incident_id.startswith("INC-"):
        if data_type not in LEGACY_PATHS:
            raise ValueError(f"Unsupported incident data type: {data_type}")

        directory, suffix = LEGACY_PATHS[data_type]
        return directory / f"{incident_id}{suffix}"

    if data_type not in EXTERNAL_FILENAMES:
        raise ValueError(f"Unsupported incident data type: {data_type}")

    return EXTERNAL_RCAEVAL_PATH / incident_id / EXTERNAL_FILENAMES[data_type]
