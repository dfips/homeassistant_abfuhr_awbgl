"""Tests for diagnostics."""

from __future__ import annotations

from custom_components.abfuhr_awbgl.const import (
    CONF_ORTSTEIL,
    CONF_PLZ,
    CONF_STREET_NAME,
)
from custom_components.abfuhr_awbgl.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_location(hass, fake_client, config_entry) -> None:
    """Diagnostics never expose the configured street, postal code or district."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    assert diagnostics["entry"]["title"] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_STREET_NAME] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_PLZ] == "**REDACTED**"
    assert diagnostics["entry"]["data"][CONF_ORTSTEIL] == "**REDACTED**"
    assert diagnostics["coordinator"]["termine_count"] > 0
    assert diagnostics["coordinator"]["next_dates"]
    assert "Musterstraße" not in str(diagnostics)
    assert "12345" not in str(diagnostics)
