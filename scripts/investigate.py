import argparse

from src.agent.graph import build_incident_graph


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--incident_id", required=True)
    args = parser.parse_args()

    graph = build_incident_graph()
    initial_state = {
        "messages": [],
        "incident_id": args.incident_id,
        "incident": {},
        "collected_evidence": [],
        "report": None,
        "tool_call_count": 0,
        "errors": [],
    }

    result = graph.invoke(initial_state, config={"recursion_limit": 30})
    print(result["report"].model_dump_json(indent=2))


if __name__ == "__main__":
    main()
