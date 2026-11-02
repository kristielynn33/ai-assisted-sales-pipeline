import csv
from pathlib import Path
from tempfile import NamedTemporaryFile

from contracts import SalesRecord
from tools.cleaning_tools import clean_and_validate_csv
from tools.file_tools import read_and_validate_csv


def export_clean_csv(source_path: Path, output_path: Path) -> int:
    """Clean, validate, and safely save a CSV for downstream use."""

    if source_path.resolve() == output_path.resolve():
        raise ValueError("The source and output files must be different.")

    # Validate every row before attempting to save anything.
    records = clean_and_validate_csv(source_path)

    # Create the output folder if it does not already exist.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        # Write to a temporary file first.
        # This prevents an incomplete file becoming the final output.
        with NamedTemporaryFile(
            mode="w",
            newline="",
            encoding="utf-8-sig",
            dir=output_path.parent,
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            writer = csv.DictWriter(
                temporary_file,
                fieldnames=list(SalesRecord.model_fields),
            )

            writer.writeheader()

            for record in records:
                writer.writerow(record.model_dump(mode="json"))

        # Read the saved data back and check that nothing changed.
        saved_records = read_and_validate_csv(temporary_path)

        if saved_records != records:
            raise ValueError(
                "Export verification failed: saved records changed."
            )

        # Publish the finished file only after verification succeeds.
        temporary_path.replace(output_path)

    finally:
        # Remove the temporary file if an error interrupted the export.
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return len(records)


if __name__ == "__main__":
    project_folder = Path(__file__).resolve().parent.parent

    source_file = (
        project_folder / "examples" / "messy_sales.csv"
    )

    output_file = (
        project_folder / "data" / "tableau_ready" / "sales_clean.csv"
    )

    row_count = export_clean_csv(source_file, output_file)

    print(
        f"SUCCESS: {row_count} rows cleaned, exported, and rechecked."
    )
    print(f"Output file: {output_file}")