from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from state import AgentState
from tools.export_tools import export_clean_csv
from tools.file_tools import read_and_validate_csv


PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def ingestion_node(state: AgentState) -> dict[str, Any]:
    """Run ordinary ingestion or explicitly requested header review."""

    raw_file_path = state.get("raw_file_path")

    if not raw_file_path:
        raise ValueError("No input CSV file was provided.")

    source_file = Path(raw_file_path)
    review_requested = state.get("review_headers", False)

    # Keep reviewed output separate from ordinary output.
    output_name = (
        "sales_reviewed.csv"
        if review_requested
        else "sales_clean.csv"
    )

    output_file = (
        PROJECT_FOLDER / "data" / "tableau_ready" / output_name
    )

    if review_requested:
        # Import the AI review tool only for this explicitly chosen route.
        from tools.review_mapping import review_and_export_csv

        row_count = review_and_export_csv(
            source_file,
            output_file,
        )

        if row_count is None:
            # Do not treat an older output file as this run's success.
            return {
                "current_agent": "IngestionAgent",
                "cleaned_records": None,
                "validation_errors": [],
                "artifacts": {},
                "messages": [
                    AIMessage(
                        content="No approved export was completed."
                    )
                ],
            }

    else:
        # Ordinary ingestion remains offline.
        row_count = export_clean_csv(
            source_file,
            output_file,
        )

    records = read_and_validate_csv(output_file)

    return {
        "current_agent": "IngestionAgent",
        "cleaned_records": [
            record.model_dump(mode="json")
            for record in records
        ],
        "validation_errors": [],
        "artifacts": {
            **state.get("artifacts", {}),
            "csv_path": str(output_file),
            "row_count": row_count,
        },
        "messages": [
            AIMessage(
                content=(
                    f"Ingestion completed: {row_count} rows "
                    "cleaned, validated, and exported."
                )
            )
        ],
    }