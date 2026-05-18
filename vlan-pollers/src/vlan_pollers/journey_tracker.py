from __future__ import annotations

from datetime import UTC, datetime


class JourneyTracker:
    """Records journey_start_date on first-seen trip_number (ADR-2).

    The start date is frozen at first-seen and never re-derived from wall-clock,
    preventing midnight-crossing journey_id flips.
    """

    def __init__(self) -> None:
        self._start_dates: dict[str, str] = {}  # trip_number → YYYYMMDD

    def get_journey_id(self, vehicle_id: str, trip_number: str) -> str:
        if trip_number not in self._start_dates:
            self._start_dates[trip_number] = datetime.now(UTC).strftime("%Y%m%d")
        return f"{vehicle_id}_{trip_number}_{self._start_dates[trip_number]}"

    def current_journey_id(self, vehicle_id: str, trip_number: str) -> str:
        """Return the journey_id without recording a new one (trip_number must exist)."""
        date = self._start_dates.get(trip_number, datetime.now(UTC).strftime("%Y%m%d"))
        return f"{vehicle_id}_{trip_number}_{date}"

    def known_trips(self) -> list[str]:
        return list(self._start_dates.keys())
