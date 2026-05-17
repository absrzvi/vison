from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubscriptionRequest:
    event_types: list[str]
    min_severity: str  # "info" | "warning" | "critical"
    coach_ids: list[str] | None = None  # None = all coaches
    reconnect_replay_depth: int = 50

    def matches_severity(self, severity: str) -> bool:
        order = {"info": 0, "warning": 1, "critical": 2}
        return order.get(severity, -1) >= order.get(self.min_severity, 0)

    def matches_event_type(self, event_type: str) -> bool:
        return event_type in self.event_types

    def matches_coach(self, coach_id: str | None) -> bool:
        if self.coach_ids is None:
            return True
        if coach_id is None:
            return True
        return coach_id in self.coach_ids

    def matches(self, event_type: str, severity: str, coach_id: str | None = None) -> bool:
        return (
            self.matches_event_type(event_type)
            and self.matches_severity(severity)
            and self.matches_coach(coach_id)
        )
