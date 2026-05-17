from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class PISMessage:
    car_id: str
    message: str
    duration_s: int = 30


class PISAdapter(Protocol):
    async def display_message(self, msg: PISMessage) -> None: ...

    async def clear_message(self, car_id: str) -> None: ...
