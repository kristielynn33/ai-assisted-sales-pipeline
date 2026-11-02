import csv
from datetime import date

import duckdb
import pytest

from tools.reconciliation_tools import verified_revenue_by_region
from tools.tableau_tools import COLUMNS


def write_snapshot(file_path, rows):
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(COLUMNS)
        writer.writerows(rows)


@pytest.fixture
def reporting_files(tmp_path):
    """Create temporary warehouse and published CSV data."""

    database_file = tmp_path / "warehouse.duckdb"

    published_file = (
        tmp_path / "tableau_ready" / "monthly_metrics.csv"
    )

    rows = [
        [
            "2024-01-01", "North", "Electronics",
            "Enterprise", 1250.50, 45, 1,
        ],
        [
            "2024-01-01", "South", "Software",
            "SMB", 3400.00, 12, 1,
        ],
        [
            "2024-02-01", "East", "Hardware",
            "Enterprise", 2800.75, 30, 1,
        ],
    ]

    connection = duckdb.connect(str(database_file))

    try:
        connection.execute(
            """
            CREATE TABLE fct_monthly_metrics (
                metric_month DATE,
                region VARCHAR,
                product_category VARCHAR,
                customer_segment VARCHAR,
                revenue DOUBLE,
                units_sold BIGINT,
                source_record_count BIGINT
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO fct_monthly_metrics
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    finally:
        connection.close()

    write_snapshot(published_file, rows)

    return database_file, published_file, rows


def check_january(database_file):
    return verified_revenue_by_region(
        database_file,
        start_month=date(2024, 1, 1),
        end_month=date(2024, 2, 1),
    )


def test_matching_period_and_regions_pass(
    reporting_files,
    capsys,
):
    database_file, _, _ = reporting_files

    results = check_january(database_file)

    assert results == [
        ("North", 1250.50),
        ("South", 3400.00),
    ]
    assert "RECONCILED:" in capsys.readouterr().out


def test_shifted_regional_totals_fail(reporting_files):
    database_file, published_file, rows = reporting_files

    # Keep the same grand total, but put money in the wrong regions.
    rows[0][4] = 1200.50
    rows[1][4] = 3450.00

    write_snapshot(published_file, rows)

    with pytest.raises(
        ValueError,
        match="RECONCILIATION FAILED",
    ):
        check_january(database_file)


def test_extra_zero_revenue_region_fails(reporting_files):
    database_file, published_file, rows = reporting_files

    rows.append(
        [
            "2024-01-01", "West", "Hardware",
            "SMB", 0.0, 0, 1,
        ]
    )

    write_snapshot(published_file, rows)

    with pytest.raises(ValueError, match="Regions differ"):
        check_january(database_file)


def test_missing_published_file_fails(reporting_files):
    database_file, published_file, _ = reporting_files

    published_file.unlink()

    with pytest.raises(FileNotFoundError):
        check_january(database_file)


def test_non_finite_published_revenue_fails(reporting_files):
    database_file, published_file, rows = reporting_files

    rows[0][4] = "NaN"
    write_snapshot(published_file, rows)

    with pytest.raises(ValueError, match="finite"):
        check_january(database_file)


def test_empty_period_is_not_reported_as_verified(reporting_files):
    database_file, _, _ = reporting_files

    with pytest.raises(
        ValueError,
        match="No reporting records",
    ):
        verified_revenue_by_region(
            database_file,
            start_month=date(2025, 1, 1),
            end_month=date(2025, 2, 1),
        )