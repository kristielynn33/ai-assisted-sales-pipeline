import json
import sys
from unittest.mock import MagicMock

import pytest

import cli
from tools import run_reports


@pytest.fixture(autouse=True)
def temporary_report_folder(tmp_path, monkeypatch):
    """Keep all test reports away from the real project data."""

    monkeypatch.setattr(
        run_reports,
        "PROJECT_FOLDER",
        tmp_path,
    )


def test_success_report_contents(tmp_path):
    source_file = tmp_path / "source.csv"
    output_file = tmp_path / "clean.csv"

    report_file = run_reports.write_run_report(
        source_file,
        status="success",
        review_headers=False,
        output_file=output_file,
        row_count=3,
    )

    report = json.loads(
        report_file.read_text(encoding="utf-8")
    )

    assert report["status"] == "success"
    assert report["source_file"] == str(source_file)
    assert report["output_file"] == str(output_file)
    assert report["row_count"] == 3
    assert report["review_headers"] is False
    assert report["error_type"] is None

    assert report["run_id"]
    assert report_file.name == (
        f"run_{report['run_id']}.json"
    )

    assert report["recorded_at_utc"].endswith("+00:00")


@pytest.mark.parametrize(
    "status, error_type",
    [
        ("stopped", None),
        ("failed", "ValueError"),
    ],
)
def test_non_success_report_contents(
    tmp_path,
    status,
    error_type,
):
    report_file = run_reports.write_run_report(
        tmp_path / "source.csv",
        status=status,
        review_headers=True,
        error_type=error_type,
    )

    report = json.loads(
        report_file.read_text(encoding="utf-8")
    )

    assert report["status"] == status
    assert report["error_type"] == error_type
    assert report["review_headers"] is True

    # These reports must not claim an exported output.
    assert report["output_file"] is None
    assert report["row_count"] is None


def test_each_run_gets_a_separate_report(tmp_path):
    source_file = tmp_path / "source.csv"

    first_report = run_reports.write_run_report(
        source_file,
        status="stopped",
        review_headers=False,
    )

    second_report = run_reports.write_run_report(
        source_file,
        status="stopped",
        review_headers=False,
    )

    assert first_report != second_report
    assert first_report.is_file()
    assert second_report.is_file()


def test_report_failure_does_not_change_success_exit_code(
    tmp_path,
    monkeypatch,
    capsys,
):
    source_file = tmp_path / "source.csv"
    source_file.write_text(
        "Placeholder for a simulated workflow.",
        encoding="utf-8",
    )

    # Simulate a completed workflow.
    # This test does not actually clean or export a CSV.
    workflow = MagicMock()
    workflow.invoke.return_value = {
        "cleaned_records": [{}],
        "artifacts": {
            "csv_path": str(tmp_path / "clean.csv"),
        },
    }

    monkeypatch.setattr(
        cli,
        "build_graph",
        lambda: workflow,
    )

    def report_unavailable(*args, **kwargs):
        raise PermissionError(
            "Simulated report-folder permission problem."
        )

    monkeypatch.setattr(
        cli,
        "write_run_report",
        report_unavailable,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["cli", "ingest", str(source_file)],
    )

    exit_code = cli.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "SUCCESS: ingestion workflow completed." in captured.out
    assert (
        "WARNING: the run report could not be saved."
        in captured.err
    )