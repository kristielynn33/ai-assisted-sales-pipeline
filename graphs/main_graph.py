from langgraph.graph import END, START, StateGraph

from agents.dbt_agent import dbt_node
from agents.ingestion import ingestion_node
from agents.warehouse import warehouse_node
from state import AgentState


def route_after_ingestion(state: AgentState) -> str:
    """Stop cancelled runs or continue to the warehouse."""

    if state.get("cleaned_records") is None:
        return "finish"

    if state.get("intent") == "full_pipeline":
        return "warehouse"

    return "finish"


def build_graph(*, include_dbt: bool = False):
    """Build the workflow, optionally including dbt."""

    builder = StateGraph(AgentState)

    builder.add_node("ingestion", ingestion_node)
    builder.add_node("warehouse", warehouse_node)

    builder.add_edge(START, "ingestion")

    builder.add_conditional_edges(
        "ingestion",
        route_after_ingestion,
        {
            "warehouse": "warehouse",
            "finish": END,
        },
    )

    if include_dbt:
        builder.add_node("dbt", dbt_node)
        builder.add_edge("warehouse", "dbt")
        builder.add_edge("dbt", END)

    else:
        builder.add_edge("warehouse", END)

    return builder.compile()