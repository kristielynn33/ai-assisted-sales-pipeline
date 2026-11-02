from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from state import AgentState
from tools.warehouse_tools import load_sales_csv


PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def warehouse_node(state: AgentState) -> dict[str, Any]:
    """Load this run's validated CSV into the local warehouse."""

    # A cancelled or incomplete ingestion must not trigger a load.
    if not state.get("cleaned_records"):
        raise ValueError(
            "No validated records from this run. "
            "Warehouse load refused."
        )

    artifacts = state.get("artifacts", {})
    csv_path = artifacts.get("csv_path")

    if not csv_path:
        raise ValueError(
            "No verified output CSV was provided."
        )

    database_file = (
        PROJECT_FOLDER / "data" / "warehouse.duckdb"
    )

    # The loader validates the CSV again before changing the database.
    row_count = load_sales_csv(
        Path(csv_path),
        database_file,
    )

    return {
        "current_agent": "WarehouseAgent",
        "artifacts": {
            **artifacts,
            "warehouse_path": str(database_file),
            "warehouse_table": "raw_sales",
            "warehouse_row_count": row_count,
        },
        "messages": [
            AIMessage(
                content=(
                    f"Warehouse load completed: {row_count} rows "
                    "loaded into raw_sales."
                )
            )
        ],
    }