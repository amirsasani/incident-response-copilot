import json
import re

from src.config import INCIDENTS_PATH


INCIDENT_ID_PATTERN = re.compile(r"^INC-\d+$")


def load_incident(incident_id: str) -> dict:
    if not INCIDENT_ID_PATTERN.fullmatch(incident_id):
        raise ValueError("Invalid incident ID.")

    incident_file = INCIDENTS_PATH / f"{incident_id}.json"

    if not incident_file.exists():
        raise FileNotFoundError(f"Incident does not exist: {incident_id}")

    with incident_file.open("r", encoding="utf-8") as file:
        incident = json.load(file)

    if not isinstance(incident, dict):
        raise ValueError("Incident file must contain an object.")

    if incident.get("incident_id") != incident_id:
        raise ValueError("Incident ID does not match the filename.")

    return incident
