import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agent.state import Evidence, IncidentReport, IncidentState
from src.incidents.repository import load_incident
from src.tools.deployment_search import get_recent_deployments
from src.tools.log_search import search_logs
from src.tools.metric_search import get_metrics
from src.tools.runbook_search import search_runbooks


TOOLS = [
    search_logs,
    get_metrics,
    get_recent_deployments,
    search_runbooks,
]

TOOL_EVIDENCE_TYPES = {
    "search_logs": "log",
    "get_metrics": "metric",
    "get_recent_deployments": "deployment",
    "search_runbooks": "runbook",
}

SYSTEM_PROMPT = """
You are an incident-response investigator.

Investigate the incident using the available tools. Before finishing, inspect:
- logs;
- metrics;
- deployments before the incident;
- relevant runbooks.

Base every conclusion on tool evidence. Do not invent evidence IDs.
When sufficient evidence has been collected, provide a short factual synthesis.
""".strip()


def load_incident_node(state: IncidentState) -> dict:
    incident = load_incident(state["incident_id"])

    return {
        "incident": incident,
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
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

    return item.get("title", "Runbook evidence.")


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
            evidence_id = item.get("evidence_id")

            if not evidence_id:
                continue

            collected[evidence_id] = Evidence(
                evidence_id=evidence_id,
                evidence_type=evidence_type,
                source=item.get("service") or item.get("source") or message.name,
                summary=create_summary(item, evidence_type),
                timestamp=item.get("timestamp") or item.get("deployed_at"),
                metadata=item,
            )

    return {
        "collected_evidence": list(collected.values()),
        "tool_call_count": state["tool_call_count"] + len(recent_tool_messages),
    }


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
            SystemMessage(content="Generate an incident report using only the supplied evidence. Cite the strongest evidence for each part of the causal chain: diagnostic errors, resource saturation and the triggering deployment. Prefer direct diagnostic evidence over generic symptoms. The evidence field must contain only valid evidence IDs from the supplied evidence."),
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
