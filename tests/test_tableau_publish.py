import csv
from unittest.mock import MagicMock

import duckdb
import pytest

from agents import dbt_agent
from tools import tableau_tools


@pytest.fixture
def reporting_files(tmp_path):
    """Create a temporary reporting table, not the real warehouse."""

    database_file = tmp_path / "warehouse.duckdb"

    output_file = (
        tmp_path / "tableau_ready" / "monthly_metrics.csv"
    )

    connection = duckdb.connect(str(database_file))

    try:
        connection.execute(
            """
            CREATE TABLE fct_monthly_metrics AS
            SELECT
                DATE '2024-01-01' AS metric_month,
                'North' AS region,
                'Electronics' AS product_category,
                'Enterprise' AS customer_segment,
                CAST(1250.50 AS DOUBLE) AS revenue,
                CAST(45 AS BIGINT) AS units_sold,
                CAST(1 AS BIGINT) AS source_record_count
            """
        )

    finally:
        connection.close()

    return database_file, output_file


def test_reporting_csv_contains_expected_values(reporting_files):
    database_file, output_file = reporting_files

    count = tableau_tools.publish_monthly_csv(
        database_file,
        output_file,
    )

    with output_file.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        reader = csv.DictReader(csv_file)
        records = list(reader)

        assert reader.fieldnames == tableau_tools.COLUMNS

    assert count == 1
    assert len(records) == 1
    assert records[0]["metric_month"] == "2024-01-01"
    assert records[0]["region"] == "North"
    assert float(records[0]["revenue"]) == pytest.approx(1250.50)
    assert records[0]["units_sold"] == "45"


def test_write_failure_preserves_previous_csv(
    reporting_files,
    monkeypatch,
):
    database_file, output_file = reporting_files

    output_file.parent.mkdir(parents=True)
    output_file.write_text(
        "Previous published output.",
        encoding="utf-8",
    )
    previous_output = output_file.read_bytes()

    def broken_writer(*args, **kwargs):
        raise OSError("Simulated write failure.")

    monkeypatch.setattr(
        tableau_tools.csv,
        "writer",
        broken_writer,
    )

    with pytest.raises(OSError, match="Simulated write failure"):
        tableau_tools.publish_monthly_csv(
            database_file,
            output_file,
        )

    assert output_file.read_bytes() == previous_output
    assert list(output_file.parent.glob("*.tmp")) == []


def test_dbt_success_publishes_csv(
    reporting_files,
    monkeypatch,
):
    database_file, output_file = reporting_files

    monkeypatch.setattr(
        dbt_agent,
        "run_dbt_build",
        lambda path: {
            "passed_results": 19,
            "passed_tests": 17,
        },
    )

    result = dbt_agent.dbt_node(
        {
            "artifacts": {
                "warehouse_path": str(database_file),
                "warehouse_table": "raw_sales",
            }
        }
    )

    assert result["dbt_success"] is True
    assert result["artifacts"]["tableau_row_count"] == 1
    assert result["artifacts"]["tableau_csv_path"] == str(output_file)
    assert output_file.is_file()


def test_dbt_failure_does_not_publish(
    reporting_files,
    monkeypatch,
):
    database_file, output_file = reporting_files

    def failed_build(path):
        raise RuntimeError("Simulated failed dbt test.")

    publish = MagicMock()

    monkeypatch.setattr(
        dbt_agent,
        "run_dbt_build",
        failed_build,
    )
    monkeypatch.setattr(
        dbt_agent,
        "publish_monthly_csv",
        publish,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated failed dbt test",
    ):
        dbt_agent.dbt_node(
            {
                "artifacts": {
                    "warehouse_path": str(database_file),
                    "warehouse_table": "raw_sales",
                }
            }
        )

    publish.assert_not_called()
    assert not output_file.exists()