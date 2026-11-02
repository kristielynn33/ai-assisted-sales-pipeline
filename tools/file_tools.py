from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from contracts import SalesRecord


def read_and_validate_csv(file_path: Path) -> list[SalesRecord]:
    """Read a CSV and validate every record against our data contract."""

    # Read the file without turning text such as "NA" into missing values.
    # Keep blank rows so they are checked rather than silently skipped.
    df = pd.read_csv(
        file_path,
        keep_default_na=False,
        skip_blank_lines=False,
        on_bad_lines="error",
    )

    if df.empty:
        raise ValueError("The CSV contains no data rows.")

    # An unexpected index can indicate extra fields in the CSV rows.
    if not isinstance(df.index, pd.RangeIndex):
        raise ValueError(
            "Unexpected CSV structure. Check for extra or shifted columns."
        )

    # Confirm that the headers match our contract.
    required_columns = set(SalesRecord.model_fields)
    actual_columns = set(df.columns)

    missing_columns = sorted(required_columns - actual_columns)
    unexpected_columns = sorted(actual_columns - required_columns)

    if missing_columns or unexpected_columns:
        raise ValueError(
            f"Header mismatch. Missing columns: {missing_columns}. "
            f"Unexpected columns: {unexpected_columns}."
        )

    # Validate every row, not just a sample.
    validated_records = []

    for row_number, row in enumerate(
        df.to_dict(orient="records"),
        start=1,
    ):
        try:
            record = SalesRecord.model_validate(row)
        except ValidationError as error:
            raise ValueError(
                f"Data row {row_number} failed validation:\n{error}"
            ) from error

        validated_records.append(record)

    return validated_records


if __name__ == "__main__":
    project_folder = Path(__file__).resolve().parent.parent
    sample_file = project_folder / "examples" / "sample_sales.csv"

    records = read_and_validate_csv(sample_file)
    total_revenue = sum(record.revenue for record in records)

    print(f"SUCCESS: {len(records)} rows passed validation.")
    print(f"Total revenue: ${total_revenue:,.2f}")