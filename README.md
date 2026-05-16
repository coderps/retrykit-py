# retrykit-py

`retrykit-py` is a tiny Python retry library with safe defaults. It is designed for common retry needs that should be easy to understand in a few minutes.

Maintained by [@coderps](https://github.com/coderps).

It installs as `retrykit-py` and imports as `retrykit`, so it is easy to distinguish from sibling projects such as `retrykit-go` while keeping Python imports short.

It is intentionally small: no runtime dependencies, no framework integrations, no logging, and no policy engine.

## Installation

```bash
pip install retrykit-py
```

For local development from this repository:

```bash
pip install -e ".[dev]"
```

## Quick start

```python
from retrykit import retry

result = retry(lambda: call_external_service())
```

By default, `retrykit` tries up to 3 total attempts, including the first attempt. It retries most exceptions, but does not retry `KeyboardInterrupt`, `SystemExit`, or `asyncio.CancelledError`.

## Decorator usage

```python
from retrykit import retryable

@retryable(max_attempts=3)
def call_external_service():
    return client.fetch_data()
```

The decorator preserves function metadata such as the function name and docstring.

## Fixed backoff

```python
from retrykit import fixed_backoff, retry

result = retry(
    call_external_service,
    max_attempts=5,
    backoff=fixed_backoff(0.2),
)
```

`fixed_backoff(0.2)` waits 0.2 seconds before each retry. Negative fixed delays are treated as `0.0`.

## Exponential backoff

```python
from retrykit import exponential_backoff, retry

result = retry(
    call_external_service,
    max_attempts=4,
    backoff=exponential_backoff(base=0.1, maximum=2.0),
)
```

Exponential backoff grows as `base`, `base * 2`, `base * 4`, and so on, capped at `maximum`.

## Custom retry condition

```python
from retrykit import fixed_backoff, retry

class TemporaryError(Exception):
    pass

result = retry(
    call_external_service,
    max_attempts=5,
    backoff=fixed_backoff(0.2),
    retry_if=lambda exc: isinstance(exc, TemporaryError),
)
```

If `retry_if` returns `False`, the original exception is raised directly and is not wrapped.

## `on_retry` callback

```python
from retrykit import Attempt, retry


def record_retry(attempt: Attempt) -> None:
    print(
        "retrying after attempt",
        attempt.number,
        "of",
        attempt.max_attempts,
        "because",
        repr(attempt.error),
        "after",
        attempt.delay,
        "seconds",
    )

result = retry(call_external_service, on_retry=record_retry)
```

`on_retry` is called after a failed retryable attempt and before sleeping. It is not called after the final failed attempt.

## Error handling

```python
from retrykit import RetryError, retry

try:
    result = retry(call_external_service)
except RetryError as exc:
    print("attempts:", exc.attempts)
    print("last error:", exc.last_error)
```

When all retry attempts are exhausted, `retrykit` raises `RetryError` and chains it from the last exception. Non-retryable exceptions are raised directly.

## Async example

```python
from retrykit import async_retry, async_retryable

result = await async_retry(lambda: call_external_service_async())

@async_retryable(max_attempts=3)
async def fetch_data():
    return await call_external_service_async()
```

Async retries use `asyncio.sleep`. By default, `asyncio.CancelledError` is not retried, so task cancellation propagates normally.

## Design philosophy

- Small API surface.
- Safe defaults.
- Sync-first, with simple async support.
- Standard-library runtime only.
- Easy to test and reason about.
- Production-friendly without being a framework.

## Non-goals

`retrykit-py` does not try to replace mature retry libraries such as Tenacity. Larger libraries may be a better fit if you need complex retry policies, multiple stop/wait strategies, rich instrumentation, framework integrations, or advanced async orchestration.

`retrykit-py` does not include:

- CLI tools
- HTTP-specific helpers
- database-specific helpers
- logging or metrics
- framework integrations
- a large policy engine
