from __future__ import annotations

import math
import random
from typing import Callable

Backoff = Callable[[int], float]

_DEFAULT_BASE = 0.1
_DEFAULT_MAXIMUM = 5.0


def fixed_backoff(delay: float) -> Backoff:
    """Return a backoff that always uses the same non-negative delay."""

    sanitized_delay = max(0.0, float(delay))

    def backoff(_attempt: int) -> float:
        return sanitized_delay

    return backoff


def exponential_backoff(base: float = _DEFAULT_BASE, maximum: float = _DEFAULT_MAXIMUM) -> Backoff:
    """Return an exponential backoff capped at ``maximum`` seconds."""

    sanitized_base = float(base) if base > 0 else _DEFAULT_BASE
    sanitized_maximum = float(maximum) if maximum > 0 else _DEFAULT_MAXIMUM

    def backoff(attempt: int) -> float:
        retry_attempt = max(1, int(attempt))
        if sanitized_base >= sanitized_maximum:
            return sanitized_maximum

        max_power = math.log2(sanitized_maximum / sanitized_base)
        power = retry_attempt - 1
        if power >= max_power:
            return sanitized_maximum
        return min(sanitized_base * (2**power), sanitized_maximum)

    return backoff


def no_backoff() -> Backoff:
    """Return a backoff that never delays."""

    def backoff(_attempt: int) -> float:
        return 0.0

    return backoff


def with_jitter(backoff: Backoff | None, factor: float = 0.2) -> Backoff:
    """Wrap a backoff callable with bounded random jitter."""

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
