from datetime import datetime
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


EvidenceType = Literal["log", "metric", "trace", "deployment", "runbook"]
FaultType = Literal["cpu", "delay", "disk", "packet_loss", "memory", "socket", "unknown"]


class Evidence(BaseModel):
    evidence_id: str
    evidence_type: EvidenceType
    source: str
    summary: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentReport(BaseModel):
    incident_id: str
    affected_service: str
    fault_type: FaultType = Field(description="Primary operational fault category supported by the evidence.")
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(
        min_length=1,
        description="IDs of evidence collected through tools.",
    )
    recommended_actions: list[str] = Field(min_length=1)
    needs_human_review: bool = True


class IncidentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    incident_id: str
    incident: dict[str, Any]
    collected_evidence: list[Evidence]
    report: IncidentReport | None
    tool_call_count: int
    errors: list[str]
