import csv

import duckdb
import pytest

from tools.warehouse_tools import load_sales_csv


HEADERS = [
    "date",
    "region",
    "product_category",
    "revenue",
    "units_sold",
    "customer_segment",
]

SAMPLE_ROWS = [
    [
        "2024-01-15",
        "North",
        "Electronics",
        "1250.50",
        "45",
        "Enterprise",
    ],
    [
        "2024-01-20",
        "South",
        "Software",
        "3400.00",
        "12",
        "SMB",
    ],
    [
        "2024-02-05",
        "East",
        "Hardware",
        "2800.75",
        "30",
        "Enterprise",
    ],
]


def write_csv(file_path, rows):
    """Write an invented CSV inside a temporary test folder."""

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(HEADERS)
        writer.writerows(rows)


@pytest.fixture
def csv_and_database(tmp_path):
    """Provide separate temporary files for each test."""

    source_file = tmp_path / "sales.csv"
    database_file = tmp_path / "warehouse.duckdb"

    write_csv(source_file, SAMPLE_ROWS)

    return source_file, database_file


def fetch_sales(database_file):
    """Read the loaded records in a predictable order."""

    connection = duckdb.connect(
        str(database_file),
        read_only=True,
    )

    try:
        return connection.execute(
            """
            SELECT
                "date",
                region,
                product_category,
                revenue,
                units_sold,
                customer_segment
            FROM raw_sales
            ORDER BY "date", region
            """
        ).fetchall()

    finally:
        connection.close()


def test_valid_csv_loads_correct_data(csv_and_database):
    source_file, database_file = csv_and_database
    original_source = source_file.read_bytes()

    loaded_count = load_sales_csv(
        source_file,
        database_file,
    )

    rows = fetch_sales(database_file)

    assert database_file.is_file()
    assert loaded_count == 3
    assert len(rows) == 3

    assert sum(row[3] for row in rows) == pytest.approx(
        7451.25
    )
    assert sum(row[4] for row in rows) == 87

    assert rows[0][0].isoformat() == "2024-01-15"
    assert rows[0][1] == "North"

    # Loading must not modify the input CSV.
    assert source_file.read_bytes() == original_source


def test_repeat_load_does_not_duplicate_rows(csv_and_database):
    source_file, database_file = csv_and_database

    load_sales_csv(source_file, database_file)
    first_load = fetch_sales(database_file)

    loaded_count = load_sales_csv(
        source_file,
        database_file,
    )
    second_load = fetch_sales(database_file)

    assert loaded_count == 3
    assert len(second_load) == 3
    assert second_load == first_load


def test_new_snapshot_replaces_previous_rows(csv_and_database):
    source_file, database_file = csv_and_database

    load_sales_csv(source_file, database_file)

    replacement_rows = [
        [
            "2024-03-01",
            "West",
            "Hardware",
            "500.00",
            "5",
            "SMB",
        ]
    ]

    write_csv(source_file, replacement_rows)

    loaded_count = load_sales_csv(
        source_file,
        database_file,
    )

    rows = fetch_sales(database_file)

    assert loaded_count == 1
    assert len(rows) == 1
    assert rows[0][0].isoformat() == "2024-03-01"
    assert rows[0][1] == "West"
    assert rows[0][3] == pytest.approx(500.00)


def test_invalid_csv_preserves_previous_data(csv_and_database):
    source_file, database_file = csv_and_database

    load_sales_csv(source_file, database_file)
    previous_rows = fetch_sales(database_file)

    # Put an invalid amount in the second data row.
    invalid_rows = [row.copy() for row in SAMPLE_ROWS]
    invalid_rows[1][3] = "-100.00"

    write_csv(source_file, invalid_rows)

    with pytest.raises(
        ValueError,
        match="Data row 2 failed validation",
    ):
        load_sales_csv(source_file, database_file)

    # The previous successful load must remain unchanged.
    assert fetch_sales(database_file) == previous_rows


def test_unrelated_table_is_preserved(csv_and_database):
    source_file, database_file = csv_and_database

    connection = duckdb.connect(str(database_file))

    try:
        connection.execute(
            "CREATE TABLE load_notes (note VARCHAR)"
        )
        connection.execute(
            "INSERT INTO load_notes VALUES (?)",
            ["Keep this note."],
        )

    finally:
        connection.close()

    load_sales_csv(source_file, database_file)

    connection = duckdb.connect(
        str(database_file),
        read_only=True,
    )

    try:
        note = connection.execute(
            "SELECT note FROM load_notes"
        ).fetchone()[0]

    finally:
        connection.close()

    assert note == "Keep this note."
    assert len(fetch_sales(database_file)) == 3