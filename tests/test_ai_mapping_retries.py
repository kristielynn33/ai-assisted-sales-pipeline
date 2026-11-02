import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.genai import errors

from tools import ai_mapping
from tools.retry_tools import TemporaryServiceError, run_with_retries


HEADER_PAIRS = [
    ("Sale Date", "date"),
    ("Sales Region", "region"),
    ("Product Category", "product_category"),
    ("Revenue USD", "revenue"),
    ("Units Sold", "units_sold"),
    ("Customer Segment", "customer_segment"),
]

HEADERS = [source for source, target in HEADER_PAIRS]


def successful_response():
    """Create a simulated successful Gemini response."""

    return SimpleNamespace(
        text=json.dumps(
            {
                "status": "proposed",
                "mappings": [
                    {"source": source, "target": target}
                    for source, target in HEADER_PAIRS
                ],
                "reason": "Simulated response for testing.",
            }
        )
    )


def api_error(code):
    """Create an API error without contacting Google."""

    return errors.APIError(
        code=code,
        response_json={
            "error": {
                "code": code,
                "message": f"Simulated API error {code}.",
            }
        },
    )


@pytest.fixture(autouse=True)
def fake_gemini(monkeypatch):
    """Replace the real client, settings, and waiting."""

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False

    client_factory = MagicMock(return_value=client)
    waits = []

    # Prevent these tests from creating a real Gemini client.
    monkeypatch.setattr(
        ai_mapping.genai,
        "Client",
        client_factory,
    )

    # Use invented settings instead of reading your .env file.
    monkeypatch.setattr(
        ai_mapping,
        "dotenv_values",
        lambda path: {
            "GEMINI_API_KEY": "fake-test-key",
            "GEMINI_MODEL": "fake-test-model",
        },
    )

    # Record requested delays instead of actually waiting.
    monkeypatch.setattr(
        ai_mapping,
        "run_with_retries",
        lambda operation: run_with_retries(
            operation,
            sleep=waits.append,
        ),
    )

    return client.models.generate_content, waits, client_factory


def test_temporary_errors_recover(fake_gemini):
    request, waits, client_factory = fake_gemini

    request.side_effect = [
        api_error(503),
        api_error(504),
        successful_response(),
    ]

    proposal = ai_mapping.propose_header_mapping(HEADERS)

    assert proposal.status == "proposed"
    assert request.call_count == 3
    assert waits == [5.0, 10.0]

    # Our helper controls retries, not the SDK.
    options = client_factory.call_args.kwargs["http_options"]
    assert options.retry_options.attempts == 1


def test_temporary_errors_stop_after_three_attempts(fake_gemini):
    request, waits, _ = fake_gemini
    request.side_effect = api_error(504)

    with pytest.raises(TemporaryServiceError, match="504"):
        ai_mapping.propose_header_mapping(HEADERS)

    assert request.call_count == 3
    assert waits == [5.0, 10.0]


def test_404_is_not_retried(fake_gemini):
    request, waits, _ = fake_gemini
    request.side_effect = api_error(404)

    with pytest.raises(RuntimeError, match="404") as captured:
        ai_mapping.propose_header_mapping(HEADERS)

    assert not isinstance(
        captured.value,
        TemporaryServiceError,
    )
    assert request.call_count == 1
    assert waits == []


def test_invalid_json_is_not_retried(fake_gemini):
    request, waits, _ = fake_gemini
    request.return_value = SimpleNamespace(text="not valid JSON")

    with pytest.raises(ValueError):
        ai_mapping.propose_header_mapping(HEADERS)

    assert request.call_count == 1
    assert waits == []