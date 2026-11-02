from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.agent.graph import build_incident_graph
from src.agent.state import IncidentReport
from src.incidents.storage import validate_incident_id


class InvestigationRequest(BaseModel):
    incident_id: str


app = FastAPI(title="Incident Response Copilot", version="0.1.0")
graph = build_incident_graph()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/investigations", response_model=IncidentReport)
def investigate(request: InvestigationRequest) -> IncidentReport:
    try:
        validate_incident_id(request.incident_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        result = graph.invoke({"messages": [], "incident_id": request.incident_id, "incident": {}, "collected_evidence": [], "report": None, "tool_call_count": 0, "errors": []}, config={"recursion_limit": 30})
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail="Investigation failed.") from error

    if result["report"] is None:
        raise HTTPException(status_code=503, detail="Investigation did not produce a report.")

    return result["report"]
