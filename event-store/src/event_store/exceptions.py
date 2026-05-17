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
