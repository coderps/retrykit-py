"""Backoff strategies used by retrykit-py.

A backoff is a small callable that receives the 1-based retry number and returns
the number of seconds to wait before the next operation attempt.
"""

from __future__ import annotations

import math
import random
from typing import Callable

# Backoff callables receive retry attempt 1 before operation attempt 2, retry
# attempt 2 before operation attempt 3, and so on.
Backoff = Callable[[int], float]

_DEFAULT_BASE = 0.1
_DEFAULT_MAXIMUM = 5.0


def fixed_backoff(delay: float) -> Backoff:
    """Return a backoff that always uses the same delay.

    Args:
        delay: Delay in seconds to return for every retry. Negative values are
            treated as ``0.0`` so callers can safely pass computed values.

    Returns:
        A ``Backoff`` callable that ignores the retry number and returns the
        sanitized delay.
    """

    sanitized_delay = max(0.0, float(delay))

    def backoff(_attempt: int) -> float:
        return sanitized_delay

    return backoff


def exponential_backoff(base: float = _DEFAULT_BASE, maximum: float = _DEFAULT_MAXIMUM) -> Backoff:
    """Return an exponential backoff capped at ``maximum`` seconds.

    Args:
        base: Initial delay in seconds for retry attempt 1. Values less than or
            equal to zero fall back to ``0.1`` seconds.
        maximum: Maximum delay in seconds. Values less than or equal to zero
            fall back to ``5.0`` seconds.

    Returns:
        A ``Backoff`` callable where retry attempt 1 returns ``base``, attempt 2
        returns ``base * 2``, attempt 3 returns ``base * 4``, and each value is
        capped at ``maximum``.
    """

    sanitized_base = float(base) if base > 0 else _DEFAULT_BASE
    sanitized_maximum = float(maximum) if maximum > 0 else _DEFAULT_MAXIMUM

    def backoff(attempt: int) -> float:
        retry_attempt = max(1, int(attempt))
        if sanitized_base >= sanitized_maximum:
            return sanitized_maximum

        # Avoid constructing extremely large powers for very high attempt
        # numbers. Once the exponent would exceed the cap, return the cap.
        max_power = math.log2(sanitized_maximum / sanitized_base)
        power = retry_attempt - 1
        if power >= max_power:
            return sanitized_maximum
        return min(sanitized_base * (2**power), sanitized_maximum)

    return backoff


def no_backoff() -> Backoff:
    """Return a backoff that never delays.

    Returns:
        A ``Backoff`` callable that always returns ``0.0`` seconds.
    """

    def backoff(_attempt: int) -> float:
        return 0.0

    return backoff


def with_jitter(backoff: Backoff | None, factor: float = 0.2) -> Backoff:
    """Wrap a backoff callable with bounded random jitter.

    Args:
        backoff: Base backoff to wrap. When ``None``, retrykit uses the default
            ``exponential_backoff()``.
        factor: Percentage range around the base delay. For example, a delay of
            ``1.0`` and factor ``0.2`` returns a random value from roughly
            ``0.8`` to ``1.2``. Values less than or equal to zero return the
            original backoff unchanged.

    Returns:
        A ``Backoff`` callable that adds jitter to the wrapped delay.
    """

    wrapped = backoff if backoff is not None else exponential_backoff()
    if factor <= 0:
        return wrapped

    jitter_factor = float(factor)

    def jittered(attempt: int) -> float:
        delay = max(0.0, float(wrapped(attempt)))
        lower = max(0.0, delay * (1.0 - jitter_factor))
        upper = delay * (1.0 + jitter_factor)
        return random.uniform(lower, upper)

    return jittered
