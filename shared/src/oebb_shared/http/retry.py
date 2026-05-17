from tenacity import retry, stop_after_attempt, wait_exponential, wait_random

DEFAULT_RETRY = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.5, max=30) + wait_random(0, 1),
    reraise=True,
)
