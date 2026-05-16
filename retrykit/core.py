from __future__ import annotations

import asyncio
import functools
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from .backoff import Backoff, exponential_backoff
from .errors import RetryError

T = TypeVar("T")

RetryIf = Callable[[BaseException], bool]
_DEFAULT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Attempt:
    """Information about a failed attempt before the next retry."""

    number: int
    max_attempts: int
    error: BaseException
    delay: float


def default_retry_if(error: BaseException) -> bool:
    """Return whether ``error`` should be retried by default."""

    return not isinstance(error, (KeyboardInterrupt, SystemExit, asyncio.CancelledError))


def retry(
    operation: Callable[[], T],
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    backoff: Backoff | None = None,
    retry_if: RetryIf | None = None,
    on_retry: Callable[[Attempt], None] | None = None,
) -> T:
    """Run ``operation`` until it succeeds, becomes non-retryable, or exhausts attempts."""

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

    raise RuntimeError("retry loop exited unexpectedly")


def retryable(
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    backoff: Backoff | None = None,
    retry_if: RetryIf | None = None,
    on_retry: Callable[[Attempt], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorate a synchronous function so it is retried when called."""

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
    """Await ``operation`` until it succeeds, becomes non-retryable, or exhausts attempts."""

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

    raise RuntimeError("retry loop exited unexpectedly")


def async_retryable(
    *,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    backoff: Backoff | None = None,
    retry_if: RetryIf | None = None,
    on_retry: Callable[[Attempt], None] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorate an async function so it is retried when awaited."""

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
    return max_attempts if max_attempts > 0 else _DEFAULT_MAX_ATTEMPTS


def _normalize_delay(delay: float) -> float:
    return max(0.0, float(delay))
