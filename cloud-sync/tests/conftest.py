"""Pytest configuration for cloud-sync.

On Windows, asyncio defaults to ``ProactorEventLoop`` which does NOT
implement ``add_writer`` / ``remove_writer`` — required by paho-mqtt's
socket integration that aiomqtt builds on. Force ``SelectorEventLoopPolicy``
for the test session so the MQTT integration tests can run on dev machines.

Linux/CI default selector loop is unaffected.
"""
from __future__ import annotations

import asyncio
import sys


def pytest_configure() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
