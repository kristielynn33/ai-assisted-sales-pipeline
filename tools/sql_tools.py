from datetime import date
from pathlib import Path

import duckdb


PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def revenue_by_region(
    database_file: Path,
    *,
    start_month: date,
    end_month: date,
) -> list[tuple[str, float]]:
    """Return regional revenue within a monthly reporting window."""

    if not database_file.is_file():
        raise FileNotFoundError(
            "Warehouse not found. Run the ingestion pipeline first."
        )

    # Our reporting table contains monthly aggregates.
    # Require whole-month boundaries rather than implying daily accuracy.
    if start_month.day != 1 or end_month.day != 1:
        raise ValueError(
            "Both boundaries must be the first day of a month."
        )

    if end_month <= start_month:
        raise ValueError(
            "The ending month must be after the starting month."
        )

    connection = duckdb.connect(
        str(database_file),
        read_only=True,
    )

    try:
        # Fixed SQL: dates are passed separately as parameters.
        rows = connection.execute(
            """
            SELECT
                region,
                SUM(revenue) AS total_revenue
            FROM main.fct_monthly_metrics
            WHERE metric_month >= ?
              AND metric_month < ?
            GROUP BY region
            ORDER BY region
            """,
            [start_month, end_month],
        ).fetchall()

    finally:
        connection.close()

    return [
        (region, float(revenue))
        for region, revenue in rows
    ]


def main() -> int:
    """Demonstrate a read-only question about January 2024."""

    database_file = (
        PROJECT_FOLDER / "data" / "warehouse.duckdb"
    )

    try:
        results = revenue_by_region(
            database_file,
            start_month=date(2024, 1, 1),
            end_month=date(2024, 2, 1),
        )

    except (OSError, ValueError, duckdb.Error) as error:
        print(f"FAILED: {error}")
        return 1

    if not results:
        print("No records found for January 2024.")
        return 0

    print("January 2024 revenue by region:")

    for region, revenue in results:
        print(f"{region}: ${revenue:,.2f}")

    total = sum(revenue for region, revenue in results)

    print(f"Total: ${total:,.2f}")
    print("Read-only query completed; no data was changed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())