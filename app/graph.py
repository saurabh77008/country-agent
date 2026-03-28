from typing import Any, Dict, Optional

from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from app.intent_parser import parse_intent
from app.tools import fetch_country_data
from app.synthesiser import synthesise_answer


class GraphState(TypedDict, total=False):
    user_query: str
    country_name: Optional[str]
    requested_fields: list
    raw_api_response: Optional[dict]
    extracted_data: Dict[str, Any]
    answer: str
    error: Optional[str]
    is_historical: bool
    comparison_countries: list
    ambiguous_countries: list


def _should_fetch(state: dict) -> str:
    if state.get("error"):
        return "synthesise"
    return "fetch"


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("parse_intent", parse_intent)
    graph.add_node("fetch_country_data", fetch_country_data)
    graph.add_node("synthesise_answer", synthesise_answer)

    graph.set_entry_point("parse_intent")

    graph.add_conditional_edges(
        "parse_intent",
        _should_fetch,
        {
            "fetch": "fetch_country_data",
            "synthesise": "synthesise_answer",
        },
    )

    graph.add_edge("fetch_country_data", "synthesise_answer")
    graph.add_edge("synthesise_answer", END)

    return graph.compile()


agent = build_graph()
