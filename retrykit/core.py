"""Core retry primitives for retrykit-py.

This module intentionally keeps the retry model small: an operation is attempted a
fixed number of times, an optional backoff computes the delay before each retry,
and an optional predicate decides whether an exception is retryable.
"""

from __future__ import annotations

import asyncio
import functools
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from .backoff import Backoff, exponential_backoff
from .errors import RetryError

T = TypeVar("T")

# A retry predicate receives the raised exception and returns True when retrykit
# should make another attempt. Returning False preserves and re-raises the
# original exception directly.
RetryIf = Callable[[BaseException], bool]

_DEFAULT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Attempt:
    """Information passed to ``on_retry`` before retrykit sleeps.

    Attributes:
        number: The 1-based operation attempt number that just failed.
        max_attempts: The total number of attempts allowed, including the first
            attempt.
        error: The exception raised by the failed attempt.
        delay: The delay in seconds that retrykit will wait before the next
            attempt. A delay of ``0.0`` means retrykit will not sleep.
    """

    number: int
    max_attempts: int
    error: BaseException
    delay: float


def default_retry_if(error: BaseException) -> bool:
    """Return whether ``error`` should be retried by default.

    Args:
        error: The exception raised by the operation.

    Returns:
        ``False`` for process-control and cancellation exceptions
        (``KeyboardInterrupt``, ``SystemExit``, and ``asyncio.CancelledError``),
        otherwise ``True``.
    """

    return not isinstance(error, (KeyboardInterrupt, SystemExit, asyncio.CancelledError))


def retry(
    operation: Callable[[], T],
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    backoff: Backoff | None = None,
    retry_if: RetryIf | None = None,
    on_retry: Callable[[Attempt], None] | None = None,
) -> T:
    """Run a synchronous operation until it succeeds or cannot be retried.

    Args:
        operation: A no-argument callable to execute. Its return value is
            returned immediately when it succeeds.
        max_attempts: Total number of attempts, including the initial attempt.
            Values less than or equal to zero fall back to the default of ``3``.
        backoff: Callable that receives the 1-based retry number and returns the
            delay in seconds before the next operation attempt. When omitted,
            retrykit uses ``exponential_backoff()``.
        retry_if: Callable that receives the raised exception and returns whether
            it should be retried. When omitted, retrykit uses
            ``default_retry_if``.
        on_retry: Optional callback invoked after a retryable failure and before
            sleeping for the next attempt. It is not called after the final
            failed attempt.

    Returns:
        The successful result from ``operation``.

    Raises:
        TypeError: If ``operation`` is not callable.
        RetryError: If all retry attempts are exhausted for retryable failures.
        BaseException: Re-raises the original exception directly when
            ``retry_if`` returns ``False``.
    """

    if not callable(operation):
        raise TypeError("operation must be a callable with no arguments")

    attempts = _normalize_max_attempts(max_attempts)
    delay_for = backoff if backoff is not None else exponential_backoff()
    should_retry = retry_if if retry_if is not None else default_retry_if

    for attempt_number in range(1, attempts + 1):
        try:
            return operation()
        except BaseException as error:
            if not should_retry(error):
                raise
            if attempt_number >= attempts:
                raise RetryError(attempts, error) from error

            delay = _normalize_delay(delay_for(attempt_number))
            if on_retry is not None:
                on_retry(
                    Attempt(
                        number=attempt_number,
                        max_attempts=attempts,
                        error=error,
                        delay=delay,
                    )
                )
            if delay > 0:
                time.sleep(delay)

    # The loop always returns, raises the original exception, or raises
    # RetryError. This guard keeps type checkers happy if the loop shape changes.
    raise RuntimeError("retry loop exited unexpectedly")


def retryable(
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    backoff: Backoff | None = None,
    retry_if: RetryIf | None = None,
    on_retry: Callable[[Attempt], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorate a synchronous function so it is retried when called.

    Args:
        max_attempts: Total number of attempts, including the initial call.
        backoff: Optional delay strategy used before each retry.
        retry_if: Optional predicate deciding whether a raised exception is
            retryable.
        on_retry: Optional callback invoked before each retry.

    Returns:
        A decorator that wraps the target function with ``retry`` while
        preserving the target function's metadata via ``functools.wraps``.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> T:
            return retry(
                lambda: func(*args, **kwargs),
                max_attempts=max_attempts,
                backoff=backoff,
                retry_if=retry_if,
                on_retry=on_retry,
            )

        return wrapper

    return decorator


async def async_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    backoff: Backoff | None = None,
    retry_if: RetryIf | None = None,
    on_retry: Callable[[Attempt], None] | None = None,
) -> T:
    """Await an async operation until it succeeds or cannot be retried.

    Args:
        operation: A no-argument callable returning an awaitable. The awaited
            result is returned immediately when it succeeds.
        max_attempts: Total number of attempts, including the initial attempt.
            Values less than or equal to zero fall back to the default of ``3``.
        backoff: Callable that receives the 1-based retry number and returns the
            delay in seconds before the next operation attempt. When omitted,
            retrykit uses ``exponential_backoff()``.
        retry_if: Callable that receives the raised exception and returns whether
            it should be retried. When omitted, retrykit uses
            ``default_retry_if``.
        on_retry: Optional callback invoked after a retryable failure and before
            awaiting the delay for the next attempt. It is not called after the
            final failed attempt.

    Returns:
        The successful awaited result from ``operation``.

    Raises:
        TypeError: If ``operation`` is not callable.
        RetryError: If all retry attempts are exhausted for retryable failures.
        BaseException: Re-raises the original exception directly when
            ``retry_if`` returns ``False``. This includes
            ``asyncio.CancelledError`` with the default retry predicate.
    """

    if not callable(operation):
        raise TypeError("operation must be a callable with no arguments")

    attempts = _normalize_max_attempts(max_attempts)
    delay_for = backoff if backoff is not None else exponential_backoff()
    should_retry = retry_if if retry_if is not None else default_retry_if

    for attempt_number in range(1, attempts + 1):
        try:
            return await operation()
        except BaseException as error:
            if not should_retry(error):
                raise
            if attempt_number >= attempts:
                raise RetryError(attempts, error) from error

            delay = _normalize_delay(delay_for(attempt_number))
            if on_retry is not None:
                on_retry(
                    Attempt(
                        number=attempt_number,
                        max_attempts=attempts,
                        error=error,
                        delay=delay,
                    )
                )
            if delay > 0:
                await asyncio.sleep(delay)

    # The loop always returns, raises the original exception, or raises
    # RetryError. This guard keeps type checkers happy if the loop shape changes.
    raise RuntimeError("retry loop exited unexpectedly")


def async_retryable(
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    backoff: Backoff | None = None,
    retry_if: RetryIf | None = None,
    on_retry: Callable[[Attempt], None] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorate an async function so it is retried when awaited.

    Args:
        max_attempts: Total number of attempts, including the initial call.
        backoff: Optional delay strategy used before each retry.
        retry_if: Optional predicate deciding whether a raised exception is
            retryable.
        on_retry: Optional callback invoked before each retry.

    Returns:
        A decorator that wraps the target async function with ``async_retry``
        while preserving function metadata via ``functools.wraps``.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            return await async_retry(
                lambda: func(*args, **kwargs),
                max_attempts=max_attempts,
                backoff=backoff,
                retry_if=retry_if,
                on_retry=on_retry,
            )

        return wrapper

    return decorator


def _normalize_max_attempts(max_attempts: int) -> int:
    """Return a safe attempt count, falling back to the library default."""

    return max_attempts if max_attempts > 0 else _DEFAULT_MAX_ATTEMPTS


def _normalize_delay(delay: float) -> float:
    """Return a non-negative delay in seconds."""

    return max(0.0, float(delay))
