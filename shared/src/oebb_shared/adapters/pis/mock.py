from .base import PISAdapter, PISMessage


class MockPISAdapter:
    """Deterministic test double for PISAdapter."""

    def __init__(self) -> None:
        self.messages: list[PISMessage] = []
        self.cleared: list[str] = []

    async def display_message(self, msg: PISMessage) -> None:
        self.messages.append(msg)

    async def clear_message(self, car_id: str) -> None:
        self.cleared.append(car_id)


def _assert_protocol() -> None:
    _: PISAdapter = MockPISAdapter()


_assert_protocol()
