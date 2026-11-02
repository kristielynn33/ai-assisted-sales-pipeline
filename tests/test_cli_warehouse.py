import sys
from unittest.mock import MagicMock

import pytest

import cli


@pytest.fixture
def command_setup(tmp_path, monkeypatch):
    """Simulate the workflow and reporting without real exports."""

    source_file = tmp_path / "source.csv"

    source_file.write_text(
        "date,region,product_category,revenue,"
        "units_sold,customer_segment\n"
        "2024-01-15,North,Electronics,1250.50,45,Enterprise\n",
        encoding="utf-8",
    )

    workflow = MagicMock()

    # The CLI only needs the record count for these tests.
    # Actual record validation is covered by our other tests.
    workflow.invoke.return_value = {
        "cleaned_records": [{}],
        "artifacts": {
            "csv_path": str(tmp_path / "clean.csv"),
        },
    }

    report_writer = MagicMock(
        return_value=tmp_path / "simulated_report.json"
    )

    # Prevent the CLI from running a real workflow.
    monkeypatch.setattr(
        cli,
        "build_graph",
        lambda: workflow,
    )

    # Prevent the CLI from writing real run reports.
    monkeypatch.setattr(
        cli,
        "write_run_report",
        report_writer,
    )

    def run_command(*options):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "cli",
                "ingest",
                str(source_file),
                *options,
            ],
        )

        return cli.main()

    return run_command, workflow, report_writer


def test_default_command_requests_csv_only(
    command_setup,
    capsys,
):
    run_command, workflow, report_writer = command_setup

    exit_code = run_command()
    captured = capsys.readouterr()

    starting_state = workflow.invoke.call_args.args[0]

    assert exit_code == 0
    assert starting_state["intent"] == "ingest"
    assert starting_state["review_headers"] is False

    assert "SUCCESS: ingestion workflow completed." in captured.out
    assert "Warehouse database:" not in captured.out

    assert report_writer.call_args.kwargs["status"] == "success"


def test_warehouse_flag_requests_full_pipeline(
    command_setup,
    capsys,
):
    run_command, workflow, report_writer = command_setup

    workflow.invoke.return_value["artifacts"].update(
        {
            "warehouse_path": "simulated_warehouse.duckdb",
            "warehouse_table": "raw_sales",
            "warehouse_row_count": 1,
        }
    )

    exit_code = run_command("--load-warehouse")
    captured = capsys.readouterr()

    starting_state = workflow.invoke.call_args.args[0]

    assert exit_code == 0
    assert starting_state["intent"] == "full_pipeline"
    assert starting_state["review_headers"] is False

    assert "Warehouse table: raw_sales" in captured.out
    assert "Warehouse rows: 1" in captured.out

    report_values = report_writer.call_args.kwargs
    assert report_values["status"] == "success"
    assert report_values["row_count"] == 1


def test_cancelled_review_is_not_reported_as_success(
    command_setup,
    capsys,
):
    run_command, workflow, report_writer = command_setup

    # Simulate cancellation with an older CSV path still present.
    workflow.invoke.return_value = {
        "cleaned_records": None,
        "artifacts": {
            "csv_path": "older_output.csv",
        },
    }

    exit_code = run_command(
        "--review-headers",
        "--load-warehouse",
    )

    captured = capsys.readouterr()
    starting_state = workflow.invoke.call_args.args[0]

    assert exit_code == 1
    assert starting_state["review_headers"] is True
    assert starting_state["intent"] == "full_pipeline"

    assert "STOPPED: no approved export was completed." in captured.out
    assert "SUCCESS:" not in captured.out
    assert "Warehouse database:" not in captured.out

    report_values = report_writer.call_args.kwargs
    assert report_values["status"] == "stopped"
    assert report_values["output_file"] is None
    assert report_values["row_count"] is None


@pytest.mark.parametrize(
    "warehouse_count",
    [None, 99],
    ids=["missing_details", "incorrect_row_count"],
)
def test_incomplete_warehouse_result_is_rejected(
    command_setup,
    capsys,
    warehouse_count,
):
    run_command, workflow, report_writer = command_setup

    if warehouse_count is not None:
        workflow.invoke.return_value["artifacts"].update(
            {
                "warehouse_path": "simulated_warehouse.duckdb",
                "warehouse_table": "raw_sales",
                "warehouse_row_count": warehouse_count,
            }
        )

    exit_code = run_command("--load-warehouse")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Warehouse completion details" in captured.err
    assert "SUCCESS:" not in captured.out

    report_values = report_writer.call_args.kwargs
    assert report_values["status"] == "failed"
    assert report_values["error_type"] == "RuntimeError"
    assert report_values["row_count"] is None


def test_workflow_error_is_reported_as_failure(
    command_setup,
    capsys,
):
    run_command, workflow, report_writer = command_setup

    workflow.invoke.side_effect = RuntimeError(
        "Simulated warehouse failure."
    )

    exit_code = run_command("--load-warehouse")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "FAILED: Simulated warehouse failure." in captured.err
    assert "SUCCESS:" not in captured.out

    report_values = report_writer.call_args.kwargs
    assert report_values["status"] == "failed"
    assert report_values["error_type"] == "RuntimeError"
    assert report_values["output_file"] is None