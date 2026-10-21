"""Diagnostics for the AWB Bergisch Gladbach integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ORTSTEIL, CONF_PLZ, CONF_STREET_NAME


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return privacy-friendly diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    redacted_data = dict(entry.data)
    for key in (CONF_STREET_NAME, CONF_PLZ, CONF_ORTSTEIL):
        if key in redacted_data:
            redacted_data[key] = "**REDACTED**"

    return {
        "entry": {
            "title": "**REDACTED**",
            "data": redacted_data,
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_import": data.last_import if data else None,
            "fetched_at": data.fetched_at.isoformat() if data else None,
            "termine_count": len(data.termine) if data else 0,
            "next_date": (
                coordinator.next_date.isoformat()
                if coordinator.next_date is not None
                else None
            ),
            "next_dates": [
                {
                    "date": datum.isoformat(),
                    "fractions": [
                        coordinator.fraction_name(termin.fraktion_id)
                        for termin in termine
                    ],
                }
                for datum, termine in coordinator.upcoming(5)
            ],
        },
    }
