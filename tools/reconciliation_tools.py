import csv
import math
from datetime import date
from pathlib import Path

import duckdb

from tools.sql_tools import revenue_by_region
from tools.tableau_tools import COLUMNS


def verified_revenue_by_region(
    database_file: Path,
    *,
    start_month: date,
    end_month: date,
) -> list[tuple[str, float]]:
    """Compare warehouse revenue with the published Tableau CSV."""

    results = revenue_by_region(
        database_file,
        start_month=start_month,
        end_month=end_month,
    )

    published_file = (
        database_file.parent
        / "tableau_ready"
        / "monthly_metrics.csv"
    )

    published_totals = {}

    # Read locally. Nothing is sent to Gemini.
    with published_file.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        reader = csv.DictReader(csv_file, strict=True)

        if reader.fieldnames != COLUMNS:
            raise ValueError(
                "The published CSV has unexpected headers."
            )

        for row_number, row in enumerate(reader, start=1):
            if None in row or any(
                value is None for value in row.values()
            ):
                raise ValueError(
                    f"Published CSV row {row_number} is malformed."
                )

            month = date.fromisoformat(row["metric_month"])

            if month.day != 1:
                raise ValueError(
                    "Published reporting dates must be month boundaries."
                )

            region = row["region"]

            if not region.strip():
                raise ValueError(
                    "The published CSV contains an empty region."
                )

            amount = float(row["revenue"])

            if not math.isfinite(amount) or amount < 0:
                raise ValueError(
                    "Published revenue must be finite and non-negative."
                )

            # Apply exactly the same period as the warehouse query.
            if start_month <= month < end_month:
                total = published_totals.get(region, 0.0) + amount

                if not math.isfinite(total):
                    raise ValueError(
                        "The published revenue total is not finite."
                    )

                published_totals[region] = total

    warehouse_totals = dict(results)

    if any(
        not math.isfinite(amount)
        for amount in warehouse_totals.values()
    ):
        raise ValueError(
            "The warehouse returned a non-finite revenue total."
        )

    if not warehouse_totals and not published_totals:
        raise ValueError(
            "No reporting records were found for this period. "
            "There is no answer to reconcile."
        )

    # Compare region membership too, including zero-revenue regions.
    if set(warehouse_totals) != set(published_totals):
        raise ValueError(
            "RECONCILIATION FAILED: Regions differ between "
            "the warehouse and published CSV for this period."
        )

    for region, warehouse_amount in warehouse_totals.items():
        published_amount = published_totals[region]

        # Match the small floating-point tolerance used by our dbt test.
        if not math.isclose(
            warehouse_amount,
            published_amount,
            rel_tol=0.0,
            abs_tol=0.000001,
        ):
            raise ValueError(
                f"RECONCILIATION FAILED for {region}: "
                f"warehouse={warehouse_amount}, "
                f"published CSV={published_amount}."
            )

    print(
        "RECONCILED: Regional revenue matches monthly_metrics.csv "
        "for the selected period."
    )

    return results


def main() -> int:
    """Check January 2024 without making an AI request."""

    project_folder = Path(__file__).resolve().parent.parent
    database_file = project_folder / "data" / "warehouse.duckdb"

    try:
        results = verified_revenue_by_region(
            database_file,
            start_month=date(2024, 1, 1),
            end_month=date(2024, 2, 1),
        )

    except (OSError, ValueError, csv.Error, duckdb.Error) as error:
        print(f"FAILED: {error}")
        return 1

    total = sum(amount for region, amount in results)

    print(f"Verified January revenue: ${total:,.2f}")
    print("No warehouse data or CSV files were changed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())