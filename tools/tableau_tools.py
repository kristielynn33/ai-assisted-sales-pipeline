import csv
from pathlib import Path
from tempfile import NamedTemporaryFile

import duckdb


COLUMNS = [
    "metric_month",
    "region",
    "product_category",
    "customer_segment",
    "revenue",
    "units_sold",
    "source_record_count",
]


def publish_monthly_csv(
    database_file: Path,
    output_file: Path,
) -> int:
    """Export the monthly model. The workflow must run dbt first."""

    if database_file.resolve() == output_file.resolve():
        raise ValueError(
            "The database and output files must be different."
        )

    connection = duckdb.connect(
        str(database_file),
        read_only=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                CAST(metric_month AS VARCHAR) AS metric_month,
                region,
                product_category,
                customer_segment,
                revenue,
                units_sold,
                source_record_count
            FROM main.fct_monthly_metrics
            ORDER BY
                metric_month,
                region,
                product_category,
                customer_segment
            """
        ).fetchall()

    finally:
        connection.close()

    if not rows:
        raise ValueError(
            "The reporting model is empty. Publication refused."
        )

    if any(value is None for row in rows for value in row):
        raise ValueError(
            "The reporting model contains missing values."
        )

    expected_csv = [
        COLUMNS,
        *[
            [str(value) for value in row]
            for row in rows
        ],
    ]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8-sig",
            dir=output_file.parent,
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            writer = csv.writer(temporary_file)
            writer.writerows(expected_csv)

        # Verify the complete saved CSV before publishing it.
        with temporary_path.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as saved_file:
            actual_csv = list(
                csv.reader(saved_file, strict=True)
            )

        if actual_csv != expected_csv:
            raise ValueError(
                "Reporting CSV verification failed."
            )

        temporary_path.replace(output_file)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return len(rows)