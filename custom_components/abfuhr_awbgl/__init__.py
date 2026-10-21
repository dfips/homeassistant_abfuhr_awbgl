"""Home Assistant integration for AWB Bergisch Gladbach collection dates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import AbfallApiClient, Strasse
from .const import (
    CONF_EXTRA_FRAKTIONEN,
    CONF_ORTSTEIL,
    CONF_PLZ,
    CONF_RESTMUELL,
    CONF_SCAN_INTERVAL,
    CONF_STREET_ID,
    CONF_STREET_NAME,
    DEFAULT_EXTRA_FRAKTIONEN,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    MAX_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
    RESTMUELL_STANDARD,
)
from .coordinator import AbfuhrCoordinator
from .util import selected_fraction_ids

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR, Platform.CALENDAR)


@dataclass(slots=True)
class AbfuhrRuntime:
    """Runtime objects belonging to one config entry."""

    client: AbfallApiClient
    coordinator: AbfuhrCoordinator
    street: Strasse


type AbfuhrConfigEntry = ConfigEntry[AbfuhrRuntime]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AbfuhrConfigEntry) -> bool:
    """Set up AWB Bergisch Gladbach from a config entry."""
    settings = {**entry.data, **entry.options}

    street = Strasse(
        id=int(entry.data[CONF_STREET_ID]),
        name=str(entry.data[CONF_STREET_NAME]),
        plz=entry.data.get(CONF_PLZ),
        ortsteil=entry.data.get(CONF_ORTSTEIL),
        hausnummern=(),
        gueltig_bis=None,
    )

    extra_fraktionen = tuple(
        int(value)
        for value in settings.get(
            CONF_EXTRA_FRAKTIONEN,
            DEFAULT_EXTRA_FRAKTIONEN,
        )
    )
    selected_ids = selected_fraction_ids(
        str(settings.get(CONF_RESTMUELL, RESTMUELL_STANDARD)),
        extra_fraktionen,
    )

    interval_hours = int(settings.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS))
    interval_hours = max(
        MIN_SCAN_INTERVAL_HOURS,
        min(MAX_SCAN_INTERVAL_HOURS, interval_hours),
    )

    client = AbfallApiClient(async_get_clientsession(hass))
    coordinator = AbfuhrCoordinator(
        hass,
        entry,
        client,
        street,
        selected_ids,
        timedelta(hours=interval_hours),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AbfuhrRuntime(
        client=client,
        coordinator=coordinator,
        street=street,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AbfuhrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: AbfuhrConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
