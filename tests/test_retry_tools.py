import pytest

from tools.retry_tools import TemporaryServiceError, run_with_retries


def test_success_runs_once():
    calls = []
    waits = []

    def operation():
        calls.append("called")
        return "completed"

    result = run_with_retries(
        operation,
        sleep=waits.append,
    )

    assert result == "completed"
    assert len(calls) == 1
    assert waits == []


def test_temporary_failures_recover():
    calls = []
    waits = []

    def operation():
        calls.append("called")

        if len(calls) < 3:
            raise TemporaryServiceError("Simulated busy service.")

        return "recovered"

    result = run_with_retries(
        operation,
        sleep=waits.append,
    )

    assert result == "recovered"
    assert len(calls) == 3
    assert waits == [5.0, 10.0]


def test_temporary_failures_stop_after_three_attempts():
    calls = []
    waits = []

    def operation():
        calls.append("called")
        raise TemporaryServiceError("Simulated ongoing outage.")

    with pytest.raises(
        TemporaryServiceError,
        match="Simulated ongoing outage",
    ):
        run_with_retries(
            operation,
            sleep=waits.append,
        )

    assert len(calls) == 3
    assert waits == [5.0, 10.0]


def test_validation_errors_are_not_retried():
    calls = []
    waits = []

    def operation():
        calls.append("called")
        raise ValueError("Invalid mapping.")

    with pytest.raises(ValueError, match="Invalid mapping"):
        run_with_retries(
            operation,
            sleep=waits.append,
        )

    assert len(calls) == 1
    assert waits == []