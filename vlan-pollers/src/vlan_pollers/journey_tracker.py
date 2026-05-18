from __future__ import annotations

from datetime import UTC, datetime


class JourneyTracker:
    """Records journey_start_date on first-seen (vehicle_id, trip_number) pair (ADR-2).

    The start date is frozen at first-seen and never re-derived from wall-clock,
    preventing midnight-crossing journey_id flips. Keyed by (vehicle_id, trip_number)
    so recycled trip numbers on the same or different vehicles don't collide.
    """

    def __init__(self) -> None:
        self._start_dates: dict[tuple[str, str], str] = {}  # (vehicle_id, trip_number) → YYYYMMDD

    def get_journey_id(self, vehicle_id: str, trip_number: str) -> str:
        key = (vehicle_id, trip_number)
        if key not in self._start_dates:
            self._start_dates[key] = datetime.now(UTC).strftime("%Y%m%d")
        return f"{vehicle_id}_{trip_number}_{self._start_dates[key]}"

    def current_journey_id(self, vehicle_id: str, trip_number: str) -> str:
        """Return the journey_id without recording a new one (trip_number must exist)."""
        key = (vehicle_id, trip_number)
        date = self._start_dates.get(key, datetime.now(UTC).strftime("%Y%m%d"))
        return f"{vehicle_id}_{trip_number}_{date}"

    def known_trips(self) -> list[str]:
        return [trip for _, trip in self._start_dates.keys()]
