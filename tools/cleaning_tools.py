import re
from datetime import date
from pathlib import Path

import pandas as pd

from contracts import SalesRecord


# Only these known header variations are renamed.
HEADER_ALIASES = {
    "transaction_date": "date",
    "area": "region",
    "product": "product_category",
    "sales_amount": "revenue",
    "qty": "units_sold",
    "customer_type": "customer_segment",
}

REGION_CODES = {
    "N": "North",
    "S": "South",
    "E": "East",
    "W": "West",
    "C": "Central",
}


def clean_and_validate_csv(file_path: Path) -> list[SalesRecord]:
    """Apply known cleaning rules, then validate every data row."""

    # Read values as text so we control each conversion.
    df = pd.read_csv(
        file_path,
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False,
        skip_blank_lines=False,
        on_bad_lines="error",
    )

    if df.empty:
        raise ValueError("The CSV contains no data rows.")

    if not isinstance(df.index, pd.RangeIndex):
        raise ValueError(
            "Unexpected CSV structure. Check for extra or shifted columns."
        )

    # Normalize headers and apply only our approved aliases.
    normalized_columns = []

    for column in df.columns:
        normalized = re.sub(r"\s+", "_", column.strip().lower())
        normalized_columns.append(
            HEADER_ALIASES.get(normalized, normalized)
        )

    if len(normalized_columns) != len(set(normalized_columns)):
        raise ValueError("Multiple headers map to the same column.")

    df.columns = normalized_columns

    required = set(SalesRecord.model_fields)
    actual = set(df.columns)

    if actual != required:
        raise ValueError(
            f"Header mismatch. Missing: {sorted(required - actual)}. "
            f"Unexpected: {sorted(actual - required)}."
        )

    validated_records = []

    for row_number, raw_row in enumerate(
        df.to_dict(orient="records"),
        start=1,
    ):
        try:
            cleaned = {
                name: value.strip()
                for name, value in raw_row.items()
            }

            # Accept year-first dates only; never guess day/month order.
            date_text = cleaned["date"].replace("/", "-")

            if not re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}",
                date_text,
            ):
                raise ValueError(
                    "Date must use YYYY-MM-DD or YYYY/MM/DD."
                )

            cleaned["date"] = date.fromisoformat(date_text)

            # Standardize known region names and abbreviations.
            region = cleaned["region"].title()
            cleaned["region"] = REGION_CODES.get(region, region)

            # This demo assumes all revenue is in US dollars.
            # Reject unfamiliar formats instead of guessing.
            revenue_text = cleaned["revenue"]
            money_pattern = (
                r"\$?[+-]?"
                r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)"
                r"(?:\.[0-9]{1,2})?"
            )

            if not re.fullmatch(money_pattern, revenue_text):
                raise ValueError(
                    f"Unsupported revenue format: {revenue_text!r}"
                )

            cleaned["revenue"] = float(
                revenue_text.replace("$", "").replace(",", "")
            )

            # Convert whole numbers without truncating decimals.
            units_text = cleaned["units_sold"]

            if not re.fullmatch(r"[+-]?[0-9]+", units_text):
                raise ValueError(
                    f"Units must be a whole number: {units_text!r}"
                )

            cleaned["units_sold"] = int(units_text)

            # The contract checks all fields after cleaning.
            record = SalesRecord.model_validate(cleaned)

        except ValueError as error:
            raise ValueError(
                f"Data row {row_number} failed:\n{error}"
            ) from error

        validated_records.append(record)

    return validated_records


if __name__ == "__main__":
    project_folder = Path(__file__).resolve().parent.parent
    sample_file = project_folder / "examples" / "messy_sales.csv"

    records = clean_and_validate_csv(sample_file)
    total_revenue = sum(record.revenue for record in records)

    print(f"SUCCESS: {len(records)} messy rows cleaned and validated.")
    print(f"Total revenue: ${total_revenue:,.2f}")
    print(f"First cleaned date: {records[0].date.isoformat()}")
    print(f"First cleaned region: {records[0].region}")