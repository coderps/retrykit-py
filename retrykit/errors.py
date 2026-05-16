"""Custom exception types for retrykit-py."""

from __future__ import annotations


class RetryError(Exception):
    """Raised when an operation fails after all retry attempts.

    Args:
        attempts: Number of operation attempts that were made.
        last_error: The final exception raised by the operation. The retry
            helpers also chain ``RetryError`` from this exception so standard
            traceback tools can show the original cause.

    Attributes:
        attempts: Number of operation attempts that were made.
        last_error: The final exception raised by the operation.
    """

    def __init__(self, attempts: int, last_error: BaseException):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"operation failed after {attempts} attempts: {last_error!r}"
        )
