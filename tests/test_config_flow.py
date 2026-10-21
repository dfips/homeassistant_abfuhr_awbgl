"""Tests for the config and options flow."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType, InvalidData
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.abfuhr_awbgl.const import (
    CONF_EXTRA_FRAKTIONEN,
    CONF_PLZ,
    CONF_RESTMUELL,
    CONF_SCAN_INTERVAL,
    CONF_STREET,
    CONF_STREET_ID,
    DOMAIN,
)

from .conftest import ENTRY_DATA, ENTRY_OPTIONS


async def _start_user_flow(hass, street: str = "Musterstraße", plz: str = "12345"):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STREET: street, CONF_PLZ: plz},
    )


async def test_user_flow_creates_entry(hass, fake_client) -> None:
    """A unique street creates a config entry."""
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_RESTMUELL: "standard",
            CONF_EXTRA_FRAKTIONEN: ["3", "4", "5"],
            CONF_SCAN_INTERVAL: 12,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Musterstraße (12345)"
    assert result["data"][CONF_STREET_ID] == 100
    assert result["options"][CONF_RESTMUELL] == "standard"
    assert result["options"][CONF_EXTRA_FRAKTIONEN] == [3, 4, 5]


async def test_ambiguous_street_requires_selection(hass, fake_client) -> None:
    """Duplicate street names are resolved with a selection step."""
    result = await _start_user_flow(hass, plz="")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "street_select"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STREET_ID: "102"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_RESTMUELL: "standard",
            CONF_EXTRA_FRAKTIONEN: ["3"],
            CONF_SCAN_INTERVAL: 12,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STREET_ID] == 102
    assert result["title"] == "Musterstraße (12346)"


async def test_street_not_found(hass, fake_client) -> None:
    """An unknown street shows a helpful error."""
    result = await _start_user_flow(hass, street="Unbekannt", plz="")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "street_not_found"}


async def test_cannot_connect(hass, fake_client) -> None:
    """An API failure is reported on the form."""
    fake_client.fail = True
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_entry_aborts(hass, fake_client) -> None:
    """The same street cannot be configured twice."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        title="Musterstraße (12345)",
        unique_id=f"{DOMAIN}_100",
    )
    existing.add_to_hass(hass)

    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_RESTMUELL: "standard",
            CONF_EXTRA_FRAKTIONEN: ["3"],
            CONF_SCAN_INTERVAL: 12,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_restmuell(hass, fake_client) -> None:
    """The selector schema rejects an invalid residual waste variant."""
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_RESTMUELL: "invalid",
                CONF_EXTRA_FRAKTIONEN: ["3"],
                CONF_SCAN_INTERVAL: 12,
            },
        )


async def test_options_flow_updates_settings(
    hass,
    fake_client,
    config_entry,
) -> None:
    """Options can be changed without creating a new entry."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_RESTMUELL: "alle",
            CONF_EXTRA_FRAKTIONEN: ["3", "6"],
            CONF_SCAN_INTERVAL: 6,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_RESTMUELL] == "alle"
    assert config_entry.options[CONF_EXTRA_FRAKTIONEN] == [3, 6]
    assert config_entry.options[CONF_SCAN_INTERVAL] == 6
