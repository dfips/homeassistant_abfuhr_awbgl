"""Tests for setting up the integration and its entities."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.abfuhr_awbgl.api import Ort, Strasse
from custom_components.abfuhr_awbgl.const import (
    CONF_EXTRA_FRAKTIONEN,
    CONF_ORT_ID,
    CONF_RESTMUELL,
    CONF_SCAN_INTERVAL,
    CONF_STREET_ID,
    CONF_STREET_STATIC_ID,
    DOMAIN,
    WEEKDAYS_DE,
)

from .conftest import ENTRY_DATA, ENTRY_OPTIONS


def _entity_id(hass, entry, platform: str, suffix: str) -> str | None:
    registry = er.async_get(hass)
    return registry.async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{suffix}")


async def test_setup_creates_sensors(hass, fake_client, config_entry) -> None:
    """Setup creates the combined sensor and one sensor per waste type."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None

    next_id = _entity_id(hass, config_entry, "sensor", "next")
    assert next_id is not None
    state = hass.states.get(next_id)
    assert state is not None
    assert state.state == (fake_client.today + timedelta(days=1)).isoformat()
    assert state.attributes["days_until"] == 1
    expected_weekday = WEEKDAYS_DE[(fake_client.today + timedelta(days=1)).weekday()]
    assert state.attributes["weekday"] == expected_weekday
    assert state.attributes["fractions"] == ["Biomüll", "Gelber Sack / Tonne"]
    assert state.attributes["street"] == "Musterstraße"
    assert state.attributes["plz"] == "12345"
    assert state.attributes["last_import"] == "01.01.2026 00:00:00"
    assert len(state.attributes["next_dates"]) == 4

    for fraktion_id, expected_days in ((0, 2), (3, 1), (4, 2), (5, 1)):
        entity_id = _entity_id(
            hass,
            config_entry,
            "sensor",
            f"fraction_{fraktion_id}",
        )
        assert entity_id is not None
        fraction_state = hass.states.get(entity_id)
        assert fraction_state is not None
        assert (
            fraction_state.state
            == (fake_client.today + timedelta(days=expected_days)).isoformat()
        )
        assert fraction_state.attributes["days_until"] == expected_days


async def test_setup_migrates_changed_api_ids(hass, fake_client) -> None:
    """Setup updates stored Ort and street IDs after an API re-import."""
    new_street = Strasse(
        id=200,
        name="Musterstraße",
        plz="12345",
        ortsteil="1a",
        hausnummern=(),
        gueltig_bis=None,
        static_id="bmV3LXN0YXRpYy1pZA==",
    )
    fake_client.orte = [Ort(id=2, name="Musterstadt")]
    fake_client.streets = [new_street]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        title="Musterstraße (12345)",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_ORT_ID] == 2
    assert entry.data[CONF_STREET_ID] == 200
    assert entry.data[CONF_STREET_STATIC_ID] == "bmV3LXN0YXRpYy1pZA=="
    assert entry.unique_id == f"{DOMAIN}_200"
    assert entry.runtime_data.street.id == 200

    next_id = _entity_id(hass, entry, "sensor", "next")
    assert next_id is not None
    state = hass.states.get(next_id)
    assert state is not None
    assert state.state == (fake_client.today + timedelta(days=1)).isoformat()


async def test_setup_retries_when_street_is_missing(hass, fake_client) -> None:
    """A missing street is not silently treated as an empty calendar."""
    fake_client.streets = []

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        title="Musterstraße (12345)",
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_all_restmuell_variants(hass, fake_client) -> None:
    """An entry with all variants creates sensors for IDs 0, 1 and 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options={
            **ENTRY_OPTIONS,
            CONF_RESTMUELL: "alle",
            CONF_EXTRA_FRAKTIONEN: [3, 4, 5],
            CONF_SCAN_INTERVAL: 12,
        },
        title="Musterstraße (12345)",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for fraktion_id in (0, 1, 2, 3, 4, 5):
        entity_id = _entity_id(
            hass,
            entry,
            "sensor",
            f"fraction_{fraktion_id}",
        )
        assert entity_id is not None
        assert entity_id in hass.states.async_entity_ids("sensor")
