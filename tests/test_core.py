import asyncio

import pytest

from retrykit import (
    Attempt,
    RetryError,
    async_retry,
    async_retryable,
    default_retry_if,
    fixed_backoff,
    no_backoff,
    retry,
    retryable,
)


def test_retry_success_on_first_attempt() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    assert retry(operation) == "ok"
    assert calls == 1


def test_retry_success_after_retries() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("temporary")
        return "ok"

    assert retry(operation, max_attempts=3, backoff=no_backoff()) == "ok"
    assert calls == 3


def test_retry_failure_after_max_attempts() -> None:
    errors: list[ValueError] = []

    def operation() -> None:
        error = ValueError("boom")
        errors.append(error)
        raise error

    with pytest.raises(RetryError) as exc_info:
        retry(operation, max_attempts=3, backoff=no_backoff())

    assert exc_info.value.attempts == 3
    assert exc_info.value.last_error is errors[-1]
    assert exc_info.value.__cause__ is errors[-1]
    assert "operation failed after 3 attempts" in str(exc_info.value)


def test_non_retryable_error_raises_original_exception_directly() -> None:
    calls = 0
    error = ValueError("do not retry")

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise error

    with pytest.raises(ValueError) as exc_info:
        retry(operation, retry_if=lambda _exc: False)

    assert exc_info.value is error
    assert calls == 1


def test_max_attempts_includes_initial_attempt() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("fail")

    with pytest.raises(RetryError) as exc_info:
        retry(operation, max_attempts=1)

    assert calls == 1
    assert exc_info.value.attempts == 1


@pytest.mark.parametrize("max_attempts", [0, -1])
def test_invalid_max_attempts_falls_back_to_default(max_attempts: int) -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("fail")

    with pytest.raises(RetryError) as exc_info:
        retry(operation, max_attempts=max_attempts, backoff=no_backoff())

    assert calls == 3
    assert exc_info.value.attempts == 3


@pytest.mark.parametrize("error", [KeyboardInterrupt(), SystemExit(), asyncio.CancelledError()])
def test_default_non_retryable_exceptions_are_not_retried(error: BaseException) -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise error

    with pytest.raises(type(error)) as exc_info:
        retry(operation)

    assert exc_info.value is error
    assert calls == 1
    assert default_retry_if(error) is False


def test_on_retry_callback_receives_attempts_before_each_retry() -> None:
    callback_attempts: list[Attempt] = []

    def operation() -> None:
        raise ValueError("temporary")

    with pytest.raises(RetryError):
        retry(
            operation,
            max_attempts=3,
            backoff=fixed_backoff(0.25),
            on_retry=callback_attempts.append,
        )

    assert [attempt.number for attempt in callback_attempts] == [1, 2]
    assert [attempt.max_attempts for attempt in callback_attempts] == [3, 3]
    assert [attempt.delay for attempt in callback_attempts] == [0.25, 0.25]
    assert all(isinstance(attempt.error, ValueError) for attempt in callback_attempts)


def test_retryable_decorator_retries_and_preserves_metadata() -> None:
    calls = 0

    @retryable(max_attempts=3, backoff=no_backoff())
    def call_service() -> str:
        """Call the service."""
        nonlocal calls
        calls += 1
        if calls < 2:
            raise RuntimeError("temporary")
        return "ok"

    assert call_service() == "ok"
    assert calls == 2
    assert call_service.__name__ == "call_service"
    assert call_service.__doc__ == "Call the service."


@pytest.mark.parametrize("operation", [None, "not callable"])
def test_retry_rejects_none_or_non_callable_operation(operation: object) -> None:
    with pytest.raises(TypeError, match="operation must be a callable"):
        retry(operation)  # type: ignore[arg-type]


def test_async_retry_success() -> None:
    async def run() -> None:
        calls = 0

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise RuntimeError("temporary")
            return "ok"

        result = await async_retry(operation, max_attempts=3, backoff=no_backoff())
        assert result == "ok"
        assert calls == 2

    asyncio.run(run())


def test_async_retry_failure() -> None:
    async def run() -> None:
        async def operation() -> None:
            raise RuntimeError("fail")

        with pytest.raises(RetryError) as exc_info:
            await async_retry(operation, max_attempts=3, backoff=no_backoff())

        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_error, RuntimeError)

    asyncio.run(run())


def test_async_retryable_decorator_retries_and_preserves_metadata() -> None:
    async def run() -> None:
        calls = 0

        @async_retryable(max_attempts=3, backoff=no_backoff())
        async def call_service() -> str:
            """Call the async service."""
            nonlocal calls
            calls += 1
            if calls < 2:
                raise RuntimeError("temporary")
            return "ok"

        assert await call_service() == "ok"
        assert calls == 2
        assert call_service.__name__ == "call_service"
        assert call_service.__doc__ == "Call the async service."

    asyncio.run(run())


def test_async_cancellation_is_not_retried() -> None:
    async def run() -> None:
        calls = 0
        error = asyncio.CancelledError()

        async def operation() -> None:
            nonlocal calls
            calls += 1
            raise error

        with pytest.raises(asyncio.CancelledError) as exc_info:
            await async_retry(operation)

        assert exc_info.value is error
        assert calls == 1

    asyncio.run(run())
