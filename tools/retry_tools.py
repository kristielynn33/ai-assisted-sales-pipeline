import time
from collections.abc import Callable
from typing import TypeVar


Result = TypeVar("Result")


class TemporaryServiceError(RuntimeError):
    """An explicitly identified temporary service outage."""


def run_with_retries(
    operation: Callable[[], Result],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> Result:
    """Try an operation at most three times for temporary outages only."""

    for attempt in range(1, 4):
        try:
            return operation()

        except TemporaryServiceError:
            # After the third failed attempt, preserve the error and stop.
            if attempt == 3:
                raise

            # Wait 5 seconds after attempt 1 and 10 after attempt 2.
            delay_seconds = 5.0 * (2 ** (attempt - 1))
            sleep(delay_seconds)

    raise RuntimeError("Retry loop ended unexpectedly.")