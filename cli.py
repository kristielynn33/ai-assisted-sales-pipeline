import argparse
import csv
import sys
from pathlib import Path

from graphs.main_graph import build_graph
from tools.run_reports import write_run_report


def main() -> int:
    """Run the requested pipeline stages and record the outcome."""

    parser = argparse.ArgumentParser(
        description="Run the data-ingestion and reporting workflow."
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    ingest_command = commands.add_parser(
        "ingest",
        help="Clean, validate, and export a sales CSV.",
    )

    ingest_command.add_argument(
        "file",
        type=Path,
        help="Path to the source CSV file.",
    )

    ingest_command.add_argument(
        "--review-headers",
        action="store_true",
        help="Offer AI header mapping with permission and approval.",
    )

    ingest_command.add_argument(
        "--load-warehouse",
        action="store_true",
        help="Replace DuckDB raw_sales with validated records.",
    )

    ingest_command.add_argument(
        "--build-mart",
        action="store_true",
        help="Load the warehouse, then build and test dbt models.",
    )

    args = parser.parse_args()
    source_file = args.file.expanduser().resolve()

    if not source_file.is_file():
        parser.error(f"Input file does not exist: {source_file}")

    warehouse_requested = (
        args.load_warehouse or args.build_mart
    )

    report_status = "failed"
    output_file = None
    row_count = None
    error_type = None
    exit_code = 1

    try:
        if args.build_mart:
            workflow = build_graph(include_dbt=True)
        else:
            workflow = build_graph()

        result = workflow.invoke(
            {
                "messages": [],
                "intent": (
                    "full_pipeline"
                    if warehouse_requested
                    else "ingest"
                ),
                "raw_file_path": str(source_file),
                "cleaned_records": None,
                "validation_errors": [],
                "retry_count": 0,
                "review_headers": args.review_headers,
                "artifacts": {},
            }
        )

        records = result.get("cleaned_records")

        if records is None:
            report_status = "stopped"
            print("STOPPED: no approved export was completed.")

        else:
            artifacts = result["artifacts"]

            if warehouse_requested and (
                not artifacts.get("warehouse_path")
                or artifacts.get("warehouse_table") != "raw_sales"
                or artifacts.get("warehouse_row_count") != len(records)
            ):
                raise RuntimeError(
                    "Warehouse completion details are "
                    "missing or inconsistent."
                )

            if args.build_mart and (
                result.get("dbt_success") is not True
                or not artifacts.get("dbt_passed_results")
            ):
                raise RuntimeError(
                    "dbt completion details are missing."
                )

            row_count = len(records)
            output_file = Path(artifacts["csv_path"])

            print("SUCCESS: ingestion workflow completed.")
            print(f"Source CSV: {source_file}")
            print(f"Validated rows: {row_count}")
            print(f"Output CSV: {output_file}")

            if warehouse_requested:
                print(
                    "Warehouse database: "
                    f"{artifacts['warehouse_path']}"
                )
                print(
                    "Warehouse table: "
                    f"{artifacts['warehouse_table']}"
                )
                print(
                    "Warehouse rows: "
                    f"{artifacts['warehouse_row_count']}"
                )

            if args.build_mart:
                print(
                    "dbt build results passed: "
                    f"{artifacts['dbt_passed_results']}"
                )
                print(
                    "dbt data tests passed: "
                    f"{artifacts['dbt_passed_tests']}"
                )

            report_status = "success"
            exit_code = 0

    except (EOFError, KeyboardInterrupt) as error:
        report_status = "stopped"
        error_type = type(error).__name__
        print("\nSTOPPED by user.", file=sys.stderr)

    except (OSError, ValueError, RuntimeError, csv.Error) as error:
        error_type = type(error).__name__
        print(f"FAILED: {error}", file=sys.stderr)

    except Exception as error:
        error_type = type(error).__name__
        print(
            f"FAILED: workflow raised {error_type}.",
            file=sys.stderr,
        )

    try:
        report_file = write_run_report(
            source_file,
            status=report_status,
            review_headers=args.review_headers,
            output_file=output_file,
            row_count=row_count,
            error_type=error_type,
        )

    except OSError:
        print(
            "WARNING: the run report could not be saved.",
            file=sys.stderr,
        )

    else:
        print(f"Run report: {report_file}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())