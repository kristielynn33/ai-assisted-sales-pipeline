import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_FOLDER = Path(__file__).resolve().parent.parent


def run_dbt_build(database_file: Path) -> dict[str, int]:
    """Run dbt and require successful models and data tests."""

    database_file = database_file.resolve()
    project_folder = PROJECT_FOLDER / "dbt_project"
    dbt_executable = Path(sys.executable).with_name("dbt.exe")

    if not database_file.is_file():
        raise ValueError("The warehouse database does not exist.")

    if not dbt_executable.is_file():
        raise ValueError(
            "dbt.exe was not found in this Python environment."
        )

    environment = os.environ.copy()
    environment["SWARM_DB_PATH"] = str(database_file)
    environment["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"

    # A fresh target directory prevents an old run_results.json
    # from being mistaken for the outcome of this run.
    with TemporaryDirectory(prefix="agent_dbt_") as folder:
        target_folder = Path(folder) / "target"

        print(
            "Running dbt models and data-quality tests...",
            flush=True,
        )

        try:
            completed = subprocess.run(
                [
                    str(dbt_executable),
                    "build",
                    "--project-dir",
                    str(project_folder),
                    "--profiles-dir",
                    str(project_folder),
                    "--target-path",
                    str(target_folder),
                ],
                cwd=str(PROJECT_FOLDER),
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                check=False,
            )

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "dbt exceeded its 300-second timeout. "
                "Check the warehouse before retrying."
            ) from None

        if completed.returncode != 0:
            details = (
                completed.stdout + "\n" + completed.stderr
            )[-4000:]

            raise RuntimeError(
                f"dbt build failed:\n{details}"
            )

        results_file = target_folder / "run_results.json"

        try:
            report = json.loads(
                results_file.read_text(encoding="utf-8")
            )
            results = report["results"]

        except (OSError, ValueError, KeyError, TypeError):
            raise RuntimeError(
                "dbt did not produce a readable results file."
            ) from None

        if (
            not isinstance(results, list)
            or not results
            or any(
                not isinstance(item, dict)
                or item.get("status") not in {"success", "pass"}
                for item in results
            )
        ):
            raise RuntimeError(
                "dbt did not report successful completion "
                "for every selected model and test."
            )

        return {
            "passed_results": len(results),
            "passed_tests": sum(
                item["status"] == "pass"
                for item in results
            ),
        }