import csv

import pytest

from tools import review_mapping
from tools.ai_mapping import ColumnMapping, HeaderProposal
from tools.file_tools import read_and_validate_csv


HEADER_MAPPING = [
    ("Sale Date", "date"),
    ("Sales Region", "region"),
    ("Product Category", "product_category"),
    ("Revenue USD", "revenue"),
    ("Units Sold", "units_sold"),
    ("Customer Segment", "customer_segment"),
]

HEADERS = [source for source, target in HEADER_MAPPING]


def write_source(file_path, units="45"):
    """Create an invented source CSV for a test."""

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(HEADERS)
        writer.writerow(
            [
                "2024/01/15",
                " n ",
                " Electronics ",
                "$1,250.50",
                units,
                " Enterprise ",
            ]
        )


@pytest.fixture
def csv_files(tmp_path):
    """Create temporary input and existing output files."""

    source_file = tmp_path / "source.csv"
    output_file = tmp_path / "reviewed.csv"

    write_source(source_file)

    output_file.write_text(
        "date,region,product_category,revenue,"
        "units_sold,customer_segment\n"
        "2023-12-01,West,Hardware,100.0,1,SMB\n",
        encoding="utf-8",
    )

    return source_file, output_file


@pytest.fixture(autouse=True)
def block_real_ai(monkeypatch):
    """Prevent these tests from using the real AI proposal function."""

    def blocked(headers):
        pytest.fail(
            "This test must use a simulated AI response."
        )

    monkeypatch.setattr(
        review_mapping,
        "propose_header_mapping",
        blocked,
    )


def answer_prompts(monkeypatch, *answers):
    """Supply test answers instead of waiting for keyboard input."""

    replies = iter(answers)

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt="": next(replies),
    )


def fake_proposal(headers):
    """Return a predictable proposal without contacting Gemini."""

    assert headers == HEADERS

    return HeaderProposal(
        status="proposed",
        mappings=[
            ColumnMapping(source=source, target=target)
            for source, target in HEADER_MAPPING
        ],
        reason="Simulated proposal for automated testing.",
    )


def test_cancel_before_request_preserves_output(
    csv_files,
    monkeypatch,
):
    source_file, output_file = csv_files
    previous_output = output_file.read_bytes()

    answer_prompts(monkeypatch, "CANCEL")

    result = review_mapping.review_and_export_csv(
        source_file,
        output_file,
    )

    assert result is None
    assert output_file.read_bytes() == previous_output


def test_cancel_after_proposal_preserves_output(
    csv_files,
    monkeypatch,
):
    source_file, output_file = csv_files
    previous_output = output_file.read_bytes()

    monkeypatch.setattr(
        review_mapping,
        "propose_header_mapping",
        fake_proposal,
    )
    answer_prompts(monkeypatch, "SEND", "CANCEL")

    result = review_mapping.review_and_export_csv(
        source_file,
        output_file,
    )

    assert result is None
    assert output_file.read_bytes() == previous_output


def test_needs_review_preserves_output(
    csv_files,
    monkeypatch,
):
    source_file, output_file = csv_files
    previous_output = output_file.read_bytes()

    def uncertain_proposal(headers):
        return HeaderProposal(
            status="needs_review",
            mappings=[],
            reason="The column meanings are uncertain.",
        )

    monkeypatch.setattr(
        review_mapping,
        "propose_header_mapping",
        uncertain_proposal,
    )
    answer_prompts(monkeypatch, "SEND")

    result = review_mapping.review_and_export_csv(
        source_file,
        output_file,
    )

    assert result is None
    assert output_file.read_bytes() == previous_output


def test_approved_export_preserves_source(
    csv_files,
    monkeypatch,
):
    source_file, output_file = csv_files
    original_source = source_file.read_bytes()

    monkeypatch.setattr(
        review_mapping,
        "propose_header_mapping",
        fake_proposal,
    )
    answer_prompts(monkeypatch, "SEND", "APPROVE")

    result = review_mapping.review_and_export_csv(
        source_file,
        output_file,
    )

    assert result == 1
    assert source_file.read_bytes() == original_source

    records = read_and_validate_csv(output_file)

    assert len(records) == 1
    assert records[0].date.isoformat() == "2024-01-15"
    assert records[0].region == "North"
    assert records[0].revenue == pytest.approx(1250.50)
    assert records[0].units_sold == 45


def test_invalid_data_preserves_previous_output(
    csv_files,
    monkeypatch,
):
    source_file, output_file = csv_files
    previous_output = output_file.read_bytes()

    # Approval must not allow fractional units through validation.
    write_source(source_file, units="2.5")

    monkeypatch.setattr(
        review_mapping,
        "propose_header_mapping",
        fake_proposal,
    )
    answer_prompts(monkeypatch, "SEND", "APPROVE")

    with pytest.raises(ValueError, match="Data row 1 failed"):
        review_mapping.review_and_export_csv(
            source_file,
            output_file,
        )

    assert output_file.read_bytes() == previous_output


def test_api_failure_preserves_previous_output(
    csv_files,
    monkeypatch,
):
    source_file, output_file = csv_files
    previous_output = output_file.read_bytes()

    def unavailable(headers):
        raise RuntimeError("Simulated temporary API outage.")

    monkeypatch.setattr(
        review_mapping,
        "propose_header_mapping",
        unavailable,
    )
    answer_prompts(monkeypatch, "SEND")

    with pytest.raises(
        RuntimeError,
        match="Simulated temporary API outage",
    ):
        review_mapping.review_and_export_csv(
            source_file,
            output_file,
        )

    assert output_file.read_bytes() == previous_output