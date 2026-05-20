"""Settings validation — empty-string secret coercion."""
from __future__ import annotations

import pytest
from pydantic import SecretStr

from cloud_sync.config import Settings


@pytest.mark.unit
def test_empty_string_event_store_api_key_coerced_to_none() -> None:
    s = Settings(event_store_api_key=SecretStr(""))
    assert s.event_store_api_key is None


@pytest.mark.unit
def test_empty_string_mqtt_username_coerced_to_none() -> None:
    s = Settings(mqtt_username=SecretStr(""))
    assert s.mqtt_username is None


@pytest.mark.unit
def test_empty_string_mqtt_password_coerced_to_none() -> None:
    s = Settings(mqtt_password=SecretStr(""))
    assert s.mqtt_password is None


@pytest.mark.unit
def test_non_empty_secret_preserved() -> None:
    s = Settings(
        event_store_api_key=SecretStr("real-key"),
        mqtt_username=SecretStr("user"),
        mqtt_password=SecretStr("pw"),
    )
    assert s.event_store_api_key is not None
    assert s.event_store_api_key.get_secret_value() == "real-key"
    assert s.mqtt_username is not None
    assert s.mqtt_username.get_secret_value() == "user"
    assert s.mqtt_password is not None
    assert s.mqtt_password.get_secret_value() == "pw"


@pytest.mark.unit
def test_defaults() -> None:
    s = Settings()
    assert s.mqtt_port == 1883
    assert s.publish_rate_per_sec == 500
    assert s.pull_batch_size == 200
    assert s.ack_interval_s == 30.0
    assert s.event_store_api_key is None


@pytest.mark.unit
def test_publish_rate_per_sec_zero_rejected() -> None:
    """Field(gt=0) constraint blocks publish_rate_per_sec=0 at config-load."""
    from pydantic import ValidationError as _VE

    with pytest.raises(_VE):
        Settings(publish_rate_per_sec=0)


@pytest.mark.unit
def test_pull_batch_size_zero_rejected() -> None:
    """Field(ge=1, le=500) blocks pull_batch_size=0."""
    from pydantic import ValidationError as _VE

    with pytest.raises(_VE):
        Settings(pull_batch_size=0)


@pytest.mark.unit
def test_pull_batch_size_above_max_rejected() -> None:
    """Field(le=500) blocks oversized batch — event-store limit."""
    from pydantic import ValidationError as _VE

    with pytest.raises(_VE):
        Settings(pull_batch_size=10_000)


@pytest.mark.unit
def test_whitespace_only_secret_coerced_to_none() -> None:
    """Whitespace-only secret is treated as unset (code-review 2026-05-20)."""
    s = Settings(mqtt_password=SecretStr("   "))
    assert s.mqtt_password is None
