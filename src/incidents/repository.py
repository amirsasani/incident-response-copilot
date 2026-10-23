import json

from src.incidents.storage import get_incident_data_file


def load_incident(incident_id: str) -> dict:
    incident_file = get_incident_data_file(incident_id, "incident")

    if not incident_file.exists():
        raise FileNotFoundError(f"Incident does not exist: {incident_id}")

    with incident_file.open("r", encoding="utf-8") as file:
        incident = json.load(file)

    if not isinstance(incident, dict):
        raise ValueError("Incident file must contain an object.")

    if incident.get("incident_id") != incident_id:
        raise ValueError("Incident ID does not match the filename.")

    return incident
