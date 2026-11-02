import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4


PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def write_run_report(
    source_file: Path,
    *,
    status: Literal["success", "stopped", "failed"],
    review_headers: bool,
    output_file: Path | None = None,
    row_count: int | None = None,
    error_type: str | None = None,
) -> Path:
    """Save workflow metadata without credentials or CSV row values."""

    report_folder = PROJECT_FOLDER / "data" / "run_reports"
    report_folder.mkdir(parents=True, exist_ok=True)

    run_id = uuid4().hex

    report = {
        "run_id": run_id,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source_file": str(source_file),
        "review_headers": review_headers,
        "output_file": (
            str(output_file) if output_file is not None else None
        ),
        "row_count": row_count,
        "error_type": error_type,
    }

    report_file = report_folder / f"run_{run_id}.json"

    report_file.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    return report_file