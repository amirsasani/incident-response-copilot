from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.agent.nodes import TOOLS, collect_evidence_node, create_investigation_node, create_report_node, load_incident_node
from src.agent.state import IncidentState
from src.config import MAX_TOOL_CALLS, OLLAMA_BASE_URL, OLLAMA_KEEP_ALIVE, OLLAMA_MODEL, OLLAMA_NUM_PREDICT, OLLAMA_REASONING


def build_incident_graph(model=None):
    model = model or ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0,
        reasoning=OLLAMA_REASONING,
        num_predict=OLLAMA_NUM_PREDICT,
        keep_alive=OLLAMA_KEEP_ALIVE,
    )

    builder = StateGraph(IncidentState)

    builder.add_node("load_incident", load_incident_node)
    builder.add_node("investigate", create_investigation_node(model, MAX_TOOL_CALLS))
    builder.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))
    builder.add_node("collect_evidence", collect_evidence_node)
    builder.add_node("generate_report", create_report_node(model))

    builder.add_edge(START, "load_incident")
    builder.add_edge("load_incident", "investigate")
    builder.add_conditional_edges("investigate", tools_condition, {"tools": "tools", "__end__": "generate_report"})
    builder.add_edge("tools", "collect_evidence")
    builder.add_edge("collect_evidence", "investigate")
    builder.add_edge("generate_report", END)

    return builder.compile()
