import csv

import pytest

from tools.cleaning_tools import clean_and_validate_csv


# A record with formatting problems our cleaner can safely fix.
SAMPLE_ROW = {
    "Transaction Date": "2024/01/15",
    "Area": " n ",
    "Product": " Electronics ",
    "Sales Amount": "$1,250.50",
    "Qty": "45",
    "Customer Type": " Enterprise ",
}


def write_test_csv(tmp_path, rows):
    """Create a temporary CSV without changing our example files."""

    file_path = tmp_path / "test_sales.csv"

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=list(SAMPLE_ROW),
        )
        writer.writeheader()
        writer.writerows(rows)

    return file_path


def test_known_formatting_is_cleaned(tmp_path):
    """Known formatting problems should be fixed correctly."""

    file_path = write_test_csv(tmp_path, [SAMPLE_ROW])
    records = clean_and_validate_csv(file_path)

    assert len(records) == 1

    record = records[0]

    assert record.date.isoformat() == "2024-01-15"
    assert record.region == "North"
    assert record.product_category == "Electronics"
    assert record.revenue == pytest.approx(1250.50)
    assert record.units_sold == 45
    assert record.customer_segment == "Enterprise"


@pytest.mark.parametrize(
    "field, bad_value",
    [
        pytest.param(
            "Sales Amount",
            "-100.00",
            id="negative_revenue",
        ),
        pytest.param(
            "Qty",
            "2.5",
            id="fractional_units",
        ),
        pytest.param(
            "Transaction Date",
            "01/02/2024",
            id="ambiguous_date",
        ),
        pytest.param(
            "Sales Amount",
            "",
            id="missing_revenue",
        ),
    ],
)
def test_bad_row_rejects_entire_file(tmp_path, field, bad_value):
    """A valid first row must not hide an invalid second row."""

    bad_row = {**SAMPLE_ROW, field: bad_value}

    file_path = write_test_csv(
        tmp_path,
        [SAMPLE_ROW, bad_row],
    )

    with pytest.raises(ValueError, match="Data row 2 failed"):
        clean_and_validate_csv(file_path)