from __future__ import annotations


class RetryError(Exception):
    """Raised when an operation fails after all retry attempts."""

    def __init__(self, attempts: int, last_error: BaseException):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"operation failed after {attempts} attempts: {last_error!r}"
        )
