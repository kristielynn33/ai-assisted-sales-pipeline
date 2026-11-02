from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from state import AgentState
from tools.dbt_tools import run_dbt_build
from tools.tableau_tools import publish_monthly_csv


def dbt_node(state: AgentState) -> dict[str, Any]:
    """Build and test reporting models, then publish their CSV."""

    artifacts = state.get("artifacts", {})
    warehouse_path = artifacts.get("warehouse_path")

    if (
        not warehouse_path
        or artifacts.get("warehouse_table") != "raw_sales"
    ):
        raise ValueError(
            "A completed warehouse load is required before dbt."
        )

    database_file = Path(warehouse_path)

    # If this fails, execution stops before publication.
    summary = run_dbt_build(database_file)

    output_file = (
        database_file.parent
        / "tableau_ready"
        / "monthly_metrics.csv"
    )

    published_rows = publish_monthly_csv(
        database_file,
        output_file,
    )

    print(f"Tableau reporting CSV: {output_file}")

    return {
        "current_agent": "DbtAgent",
        "dbt_success": True,
        "dbt_log": (
            f"dbt passed: {summary['passed_results']} results. "
            "Reporting CSV published."
        ),
        "artifacts": {
            **artifacts,
            "dbt_passed_results": summary["passed_results"],
            "dbt_passed_tests": summary["passed_tests"],
            "tableau_csv_path": str(output_file),
            "tableau_row_count": published_rows,
        },
        "messages": [
            AIMessage(
                content=(
                    "dbt models and tests passed. "
                    "Monthly reporting CSV published."
                )
            )
        ],
    }