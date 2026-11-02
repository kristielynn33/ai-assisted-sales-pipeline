import duckdb
import pytest

from agents import ingestion as ingestion_agent
from agents import warehouse as warehouse_agent
from graphs import main_graph
from tools.warehouse_tools import load_sales_csv


@pytest.fixture
def isolated_run(tmp_path, monkeypatch):
    """Redirect workflow outputs to a temporary project folder."""

    monkeypatch.setattr(
        ingestion_agent,
        "PROJECT_FOLDER",
        tmp_path,
    )

    monkeypatch.setattr(
        warehouse_agent,
        "PROJECT_FOLDER",
        tmp_path,
    )

    source_file = tmp_path / "source.csv"

    source_file.write_text(
        "date,region,product_category,revenue,"
        "units_sold,customer_segment\n"
        "2024-01-15,North,Electronics,1250.50,45,Enterprise\n",
        encoding="utf-8",
    )

    database_file = (
        tmp_path / "data" / "warehouse.duckdb"
    )

    initial_state = {
        "messages": [],
        "intent": "full_pipeline",
        "raw_file_path": str(source_file),
        "cleaned_records": None,
        "validation_errors": [],
        "retry_count": 0,
        "review_headers": False,
        "artifacts": {},
    }

    return initial_state, source_file, database_file


def test_full_pipeline_loads_warehouse(isolated_run):
    initial_state, _, database_file = isolated_run

    result = main_graph.build_graph().invoke(initial_state)

    assert result["current_agent"] == "WarehouseAgent"
    assert result["artifacts"]["warehouse_row_count"] == 1
    assert result["artifacts"]["warehouse_table"] == "raw_sales"
    assert database_file.is_file()

    connection = duckdb.connect(
        str(database_file),
        read_only=True,
    )

    try:
        row_count, revenue = connection.execute(
            "SELECT COUNT(*), SUM(revenue) FROM raw_sales"
        ).fetchone()

    finally:
        connection.close()

    assert row_count == 1
    assert revenue == pytest.approx(1250.50)


def test_csv_only_run_skips_warehouse(isolated_run):
    initial_state, _, database_file = isolated_run
    initial_state["intent"] = "ingest"

    result = main_graph.build_graph().invoke(initial_state)

    assert result["current_agent"] == "IngestionAgent"
    assert len(result["cleaned_records"]) == 1
    assert "warehouse_path" not in result["artifacts"]
    assert not database_file.exists()


def test_cancelled_ingestion_does_not_load_old_csv(
    isolated_run,
    monkeypatch,
):
    initial_state, source_file, database_file = isolated_run

    # Prepare an existing temporary warehouse snapshot.
    load_sales_csv(source_file, database_file)
    previous_database = database_file.read_bytes()

    def cancelled_ingestion(state):
        # Simulate cancellation while an older CSV path still exists.
        return {
            "current_agent": "IngestionAgent",
            "cleaned_records": None,
            "artifacts": {
                "csv_path": str(source_file),
            },
        }

    def forbidden_warehouse(state):
        pytest.fail(
            "Cancelled ingestion must not reach the warehouse node."
        )

    monkeypatch.setattr(
        main_graph,
        "ingestion_node",
        cancelled_ingestion,
    )

    monkeypatch.setattr(
        main_graph,
        "warehouse_node",
        forbidden_warehouse,
    )

    result = main_graph.build_graph().invoke(initial_state)

    assert result["cleaned_records"] is None
    assert result["current_agent"] == "IngestionAgent"

    # The existing database must remain unchanged.
    assert database_file.read_bytes() == previous_database