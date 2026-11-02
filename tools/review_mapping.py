import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.ai_mapping import propose_header_mapping
from tools.export_tools import export_clean_csv


PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def review_and_export_csv(
    source_file: Path,
    output_file: Path,
) -> int | None:
    """
    Request approval for AI header mapping, then export validated data.

    Return the exported row count after success.
    Return None if the user cancels or manual review is required.
    """

    if source_file.resolve() == output_file.resolve():
        raise ValueError(
            "The source and output files must be different."
        )

    # Read locally. No row values are sent to Gemini.
    with source_file.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        rows = list(csv.reader(csv_file, strict=True))

    if len(rows) < 2:
        raise ValueError(
            "The CSV must contain headers and at least one data row."
        )

    headers = rows[0]

    if any(not header.strip() for header in headers):
        raise ValueError("The CSV contains an empty header.")

    if len(headers) != len(set(headers)):
        raise ValueError("The CSV contains duplicate headers.")

    # Reject malformed rows instead of silently dropping fields.
    for row_number, row in enumerate(rows[1:], start=1):
        if len(row) != len(headers):
            raise ValueError(
                f"Data row {row_number} does not match "
                "the number of headers."
            )

    print("Headers found:")
    for header in headers:
        print(f"  {header}")

    print("\nOnly headers and mapping instructions go to Gemini.")
    print("CSV row values remain local.")

    permission = input(
        "\nType SEND to request an AI proposal: "
    ).strip()

    if permission != "SEND":
        print(
            "Cancelled. No AI request was sent; "
            "no CSV files were changed."
        )
        return None

    print("\nRequesting an AI proposal...")
    proposal = propose_header_mapping(headers)

    if proposal.status == "needs_review":
        print(f"REVIEW NEEDED: {proposal.reason}")
        print("No CSV files were changed.")
        return None

    print("\nProposed header mappings:")
    for mapping in proposal.mappings:
        print(f"  {mapping.source} -> {mapping.target}")

    print("\nCheck the meaning of every mapping before approving.")

    approval = input(
        "Type APPROVE to apply these header changes: "
    ).strip()

    if approval != "APPROVE":
        print("Cancelled. No CSV files were changed.")
        return None

    renames = {
        mapping.source: mapping.target
        for mapping in proposal.mappings
    }

    # Apply approved header changes to a temporary copy only.
    with TemporaryDirectory(
        prefix="agent_header_review_"
    ) as temporary_folder:
        mapped_file = (
            Path(temporary_folder) / "header_mapped.csv"
        )

        with mapped_file.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as csv_file:
            writer = csv.writer(csv_file)

            writer.writerow(
                [renames[header] for header in headers]
            )

            # Preserve the original row values.
            writer.writerows(rows[1:])

        # Use the existing cleaning and verified-export tools.
        row_count = export_clean_csv(
            mapped_file,
            output_file,
        )

    return row_count


def main() -> int:
    """Run the demonstration using our example CSV."""

    source_file = (
        PROJECT_FOLDER / "examples" / "unfamiliar_headers.csv"
    )

    output_file = (
        PROJECT_FOLDER
        / "data"
        / "tableau_ready"
        / "sales_reviewed.csv"
    )

    try:
        row_count = review_and_export_csv(
            source_file,
            output_file,
        )

    except (EOFError, KeyboardInterrupt):
        print("\nStopped by user.")
        return 1

    except (OSError, ValueError, RuntimeError) as error:
        print(f"FAILED: {error}")
        return 1

    except Exception as error:
        print(f"FAILED: operation raised {type(error).__name__}.")
        return 1

    # A cancelled or unresolved review is not a successful export.
    if row_count is None:
        return 0

    print(f"\nSUCCESS: {row_count} rows exported after approval.")
    print(f"Output CSV: {output_file}")
    print("The source CSV and sales_clean.csv were not changed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())