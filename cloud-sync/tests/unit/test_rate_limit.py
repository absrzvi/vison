"""Token bucket rate limiter."""
from __future__ import annotations

import asyncio
import time

import pytest

from cloud_sync.mqtt_client import TokenBucket


@pytest.mark.unit
async def test_token_bucket_initial_burst_is_capacity() -> None:
    """A bucket at rate=500 starts with 500 tokens; the first 500 acquires
    return immediately."""
    bucket = TokenBucket(rate=500)
    t0 = time.perf_counter()
    for _ in range(500):
        await bucket.acquire()
    elapsed = time.perf_counter() - t0
    # Initial burst should be sub-50ms (no token waiting).
    assert elapsed < 0.5, f"initial burst took {elapsed*1000:.0f}ms; rate-limit too eager"


@pytest.mark.unit
async def test_token_bucket_throttles_beyond_capacity() -> None:
    """1000 acquires at rate=500 must take ≥ ~1 second."""
    bucket = TokenBucket(rate=500)
    t0 = time.perf_counter()
    for _ in range(1000):
        await bucket.acquire()
    elapsed = time.perf_counter() - t0
    # 500 instant + 500 throttled at 1/500 = 2ms each → ~1.0s
    assert elapsed >= 0.9, f"throttled run was {elapsed*1000:.0f}ms; expected >= 900ms"


@pytest.mark.unit
def test_token_bucket_rejects_zero_rate() -> None:
    with pytest.raises(ValueError):
        TokenBucket(rate=0)


@pytest.mark.unit
def test_token_bucket_rejects_negative_rate() -> None:
    with pytest.raises(ValueError):
        TokenBucket(rate=-1)


@pytest.mark.unit
async def test_token_bucket_concurrent_acquires_serialise() -> None:
    """Two coroutines acquiring 100 tokens each from rate=200 → ~1s total."""
    bucket = TokenBucket(rate=200)
    # Drain the initial capacity first so the test exercises the throttle path.
    for _ in range(200):
        await bucket.acquire()

    async def worker(n: int) -> None:
        for _ in range(n):
            await bucket.acquire()

    t0 = time.perf_counter()
    await asyncio.gather(worker(100), worker(100))
    elapsed = time.perf_counter() - t0
    # 200 throttled tokens at rate=200 → ~1.0s
    assert elapsed >= 0.9, f"concurrent throttled run was {elapsed*1000:.0f}ms"
