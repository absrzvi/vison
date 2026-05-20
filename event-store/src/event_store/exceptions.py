from __future__ import annotations


class EventStoreError(Exception):
    """Base exception for event-store."""


class JourneyNotFoundError(EventStoreError):
    def __init__(self, journey_id: str) -> None:
        super().__init__(f"Journey not found: {journey_id}")
        self.journey_id = journey_id


class UnsupportedSchemaVersionError(EventStoreError):
    def __init__(self, version: int) -> None:
        super().__init__(f"Unsupported schema_version: {version}")
        self.version = version


class InvalidCursorError(EventStoreError):
    """The ``?after=<event_id>`` cursor references an event_id that does not
    exist. Surfaced to clients as 400 with the ADR-10 ``INVALID_CURSOR``
    envelope so paginating clients cannot infinite-loop on stale state.
    """

    def __init__(self, cursor: str) -> None:
        super().__init__(f"Cursor event_id not found: {cursor}")
        self.cursor = cursor
