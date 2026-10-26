import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agent.state import Evidence, IncidentReport, IncidentState
from src.incidents.repository import load_incident
from src.tools.deployment_search import get_recent_deployments
from src.tools.log_search import search_logs
from src.tools.metric_search import get_metrics
from src.tools.runbook_search import search_runbooks
from src.tools.trace_search import search_traces


TOOLS = [
    search_logs,
    get_metrics,
    search_traces,
    get_recent_deployments,
    search_runbooks,
]

TOOL_EVIDENCE_TYPES = {
    "search_logs": "log",
    "get_metrics": "metric",
    "search_traces": "trace",
    "get_recent_deployments": "deployment",
    "search_runbooks": "runbook",
}

DEFAULT_EVIDENCE_SOURCES = ["logs", "metrics", "deployments", "runbooks"]


def create_system_prompt(incident: dict) -> str:
    evidence_sources = incident.get("available_evidence", DEFAULT_EVIDENCE_SOURCES)
    source_list = "\n".join(f"- {source}" for source in evidence_sources)
    return f"""
You are an incident-response investigator.

Investigate the incident using the available tools. You must call the appropriate tool for every available evidence source before finishing:
{source_list}

Do not call tools for evidence sources that are not listed. Begin by collecting evidence, even when the incident description is generic. Base every conclusion on tool evidence and do not invent evidence IDs. When sufficient evidence has been collected, provide a short factual synthesis.
""".strip()


def load_incident_node(state: IncidentState) -> dict:
    incident = load_incident(state["incident_id"])

    return {
        "incident": incident,
        "messages": [
            SystemMessage(content=create_system_prompt(incident)),
            HumanMessage(content=f"Investigate this incident:\n{json.dumps(incident, indent=2)}"),
        ],
        "collected_evidence": [],
        "report": None,
        "tool_call_count": 0,
        "errors": [],
    }


def create_investigation_node(model, max_tool_calls: int):
    model_with_tools = model.bind_tools(TOOLS)

    def investigate(state: IncidentState) -> dict:
        if state["tool_call_count"] >= max_tool_calls:
            return {"messages": [AIMessage(content="The tool-call limit has been reached. Generate the report from the collected evidence.")]}

        response = model_with_tools.invoke(state["messages"])

        if not response.tool_calls and not state["collected_evidence"]:
            retry_messages = [*state["messages"], response, HumanMessage(content="No evidence has been collected. Call the tools for the incident's listed evidence sources now; do not provide a conclusion yet.")]
            response = model_with_tools.invoke(retry_messages)

        return {"messages": [response]}

    return investigate


def create_summary(item: dict, evidence_type: str) -> str:
    if evidence_type == "log":
        return item.get("message", "Log evidence.")

    if evidence_type == "metric":
        return f"{item.get('metric')} reached {item.get('value')} {item.get('unit', '')}.".strip()

    if evidence_type == "deployment":
        changes = ", ".join(item.get("changes", []))
        return f"Version {item.get('version')} was deployed. Changes: {changes}"

    if evidence_type == "trace":
        return f"{item.get('service')} {item.get('operation')} returned status {item.get('status_code')} with duration {item.get('duration')}."

    return item.get("title", "Runbook evidence.")


def create_evidence(item: dict, evidence_type: str, source: str) -> Evidence | None:
    evidence_id = item.get("evidence_id")

    if not evidence_id:
        return None

    return Evidence(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source=item.get("service") or item.get("source") or source,
        summary=create_summary(item, evidence_type),
        timestamp=item.get("timestamp") or item.get("deployed_at"),
        metadata=item,
    )


def collect_evidence_node(state: IncidentState) -> dict:
    recent_tool_messages = []

    for message in reversed(state["messages"]):
        if not isinstance(message, ToolMessage):
            break

        recent_tool_messages.append(message)

    collected = {
        evidence.evidence_id: evidence
        for evidence in state["collected_evidence"]
    }

    for message in reversed(recent_tool_messages):
        try:
            results = json.loads(message.content)
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(results, list):
            continue

        evidence_type = TOOL_EVIDENCE_TYPES.get(message.name)

        if not evidence_type:
            continue

        for item in results:
            evidence = create_evidence(item, evidence_type, message.name)

            if evidence is None:
                continue

            collected[evidence.evidence_id] = evidence

    return {
        "collected_evidence": list(collected.values()),
        "tool_call_count": state["tool_call_count"] + len(recent_tool_messages),
    }


def fallback_evidence_node(state: IncidentState) -> dict:
    incident = state["incident"]
    incident_id = state["incident_id"]
    evidence_sources = incident.get("available_evidence", DEFAULT_EVIDENCE_SOURCES)
    query = " ".join([incident.get("title", ""), incident.get("service", ""), *incident.get("symptoms", [])]).strip()
    tool_requests = {
        "logs": (search_logs, {"incident_id": incident_id, "limit": 20}, "log"),
        "metrics": (get_metrics, {"incident_id": incident_id, "limit": 20}, "metric"),
        "traces": (search_traces, {"incident_id": incident_id, "limit": 20}, "trace"),
        "deployments": (get_recent_deployments, {"service": incident.get("service", ""), "before": incident.get("started_at"), "limit": 5}, "deployment"),
        "runbooks": (search_runbooks, {"query": query, "limit": 5}, "runbook"),
    }
    collected = {evidence.evidence_id: evidence for evidence in state["collected_evidence"]}
    errors = list(state["errors"])
    tool_call_count = state["tool_call_count"]

    for source in evidence_sources:
        request = tool_requests.get(source)

        if request is None:
            errors.append(f"Unsupported fallback evidence source: {source}")
            continue

        tool, arguments, evidence_type = request
        tool_call_count += 1

        try:
            results = tool.invoke(arguments)
        except Exception as error:
            errors.append(f"Fallback {source} search failed: {type(error).__name__}: {error}")
            continue

        for item in results:
            evidence = create_evidence(item, evidence_type, tool.name)

            if evidence is not None:
                collected[evidence.evidence_id] = evidence

    if not collected:
        errors.append("Fallback evidence collection returned no evidence.")

    return {"collected_evidence": list(collected.values()), "tool_call_count": tool_call_count, "errors": errors}


def create_report_node(model):
    structured_model = model.with_structured_output(IncidentReport, method="json_schema")

    def generate_report(state: IncidentState) -> dict:
        if not state["collected_evidence"]:
            raise ValueError("Cannot generate a report without evidence.")

        context = {
            "incident": state["incident"],
            "evidence": [evidence.model_dump(mode="json") for evidence in state["collected_evidence"]],
        }

        messages = [
            SystemMessage(content="Generate an incident report using only the supplied evidence. Cite the strongest relevant evidence across the available evidence types and prefer direct diagnostic evidence over generic symptoms. The evidence field must contain only valid evidence IDs from the supplied evidence."),
            HumanMessage(content=json.dumps(context, indent=2)),
        ]

        report = structured_model.invoke(messages)

        if isinstance(report, dict):
            report = IncidentReport.model_validate(report)

        valid_evidence_ids = {evidence.evidence_id for evidence in state["collected_evidence"]}
        invalid_evidence_ids = set(report.evidence) - valid_evidence_ids

        if invalid_evidence_ids:
            raise ValueError(f"Report contains unknown evidence IDs: {sorted(invalid_evidence_ids)}")

        if report.incident_id != state["incident_id"]:
            raise ValueError("Report incident ID does not match the investigated incident.")

        return {"report": report}

    return generate_report
