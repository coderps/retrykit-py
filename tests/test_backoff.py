from retrykit import exponential_backoff, fixed_backoff, no_backoff, with_jitter


def test_fixed_backoff_returns_same_delay() -> None:
    backoff = fixed_backoff(0.25)

    assert backoff(1) == 0.25
    assert backoff(10) == 0.25


def test_fixed_backoff_negative_delay_returns_zero() -> None:
    backoff = fixed_backoff(-1)

    assert backoff(1) == 0.0


def test_exponential_backoff_grows_and_caps() -> None:
    backoff = exponential_backoff(base=0.5, maximum=2.0)

    assert backoff(1) == 0.5
    assert backoff(2) == 1.0
    assert backoff(3) == 2.0
    assert backoff(4) == 2.0


def test_exponential_backoff_invalid_values_use_defaults() -> None:
    backoff = exponential_backoff(base=0, maximum=-1)

    assert backoff(1) == 0.1
    assert backoff(2) == 0.2
    assert backoff(1000) == 5.0


def test_no_backoff_always_returns_zero() -> None:
    backoff = no_backoff()

    assert backoff(1) == 0.0
    assert backoff(100) == 0.0


def test_with_jitter_returns_value_within_expected_range() -> None:
    backoff = with_jitter(fixed_backoff(1.0), factor=0.2)

    for _ in range(100):
        assert 0.8 <= backoff(1) <= 1.2


def test_with_jitter_non_positive_factor_returns_original_behavior() -> None:
    backoff = with_jitter(fixed_backoff(1.0), factor=0)

    assert backoff(1) == 1.0
    assert backoff(2) == 1.0


def test_with_jitter_none_backoff_uses_default_exponential_backoff() -> None:
    backoff = with_jitter(None, factor=0)

    assert backoff(1) == 0.1
    assert backoff(2) == 0.2
