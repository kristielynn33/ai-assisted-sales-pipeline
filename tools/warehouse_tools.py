from pathlib import Path

import duckdb

from tools.file_tools import read_and_validate_csv


PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def load_sales_csv(
    source_file: Path,
    database_file: Path,
) -> int:
    """Load a validated CSV into a replacement raw_sales table."""

    # Validate the entire CSV before opening the database.
    records = read_and_validate_csv(source_file)

    rows = [
        (
            record.date,
            record.region,
            record.product_category,
            record.revenue,
            record.units_sold,
            record.customer_segment,
        )
        for record in records
    ]

    database_file.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(database_file))

    try:
        connection.execute("BEGIN TRANSACTION")

        connection.execute(
            """
            CREATE OR REPLACE TABLE raw_sales (
                "date" DATE NOT NULL,
                region VARCHAR NOT NULL,
                product_category VARCHAR NOT NULL,
                revenue DOUBLE NOT NULL
                    CHECK (isfinite(revenue) AND revenue >= 0),
                units_sold BIGINT NOT NULL
                    CHECK (units_sold >= 0),
                customer_segment VARCHAR NOT NULL
            )
            """
        )

        # Pass values separately from SQL instead of building SQL strings.
        connection.executemany(
            """
            INSERT INTO raw_sales (
                "date",
                region,
                product_category,
                revenue,
                units_sold,
                customer_segment
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        loaded_rows = connection.execute(
            "SELECT COUNT(*) FROM raw_sales"
        ).fetchone()[0]

        if loaded_rows != len(records):
            raise ValueError(
                "Warehouse row count does not match the source."
            )

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise

    finally:
        connection.close()

    return loaded_rows


def main() -> None:
    """Load our existing cleaned sample and display a summary."""

    source_file = (
        PROJECT_FOLDER
        / "data"
        / "tableau_ready"
        / "sales_clean.csv"
    )

    database_file = (
        PROJECT_FOLDER / "data" / "warehouse.duckdb"
    )

    row_count = load_sales_csv(
        source_file,
        database_file,
    )

    # Reopen read-only to check the saved database.
    connection = duckdb.connect(
        str(database_file),
        read_only=True,
    )

    try:
        total_revenue = connection.execute(
            "SELECT SUM(revenue) FROM raw_sales"
        ).fetchone()[0]

    finally:
        connection.close()

    print("SUCCESS: validated CSV loaded into DuckDB.")
    print("Table: raw_sales")
    print(f"Loaded rows: {row_count}")
    print(f"Total revenue: ${total_revenue:,.2f}")
    print(f"Database file: {database_file}")


if __name__ == "__main__":
    main()