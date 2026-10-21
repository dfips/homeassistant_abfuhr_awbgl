"""Shared fixtures for the AWB Bergisch Gladbach tests."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.abfuhr_awbgl.api import (
    AbfallApiConnectionError,
    AppData,
    Fraktion,
    Ort,
    Strasse,
    Termin,
)
from custom_components.abfuhr_awbgl.const import (
    CONF_EXTRA_FRAKTIONEN,
    CONF_ORT_ID,
    CONF_ORT_NAME,
    CONF_ORTSTEIL,
    CONF_PLZ,
    CONF_RESTMUELL,
    CONF_SCAN_INTERVAL,
    CONF_STREET_ID,
    CONF_STREET_NAME,
    DOMAIN,
    RESTMUELL_STANDARD,
)

pytest_plugins = ["pytest_homeassistant_custom_component"]

ENTRY_DATA = {
    CONF_ORT_ID: 1,
    CONF_ORT_NAME: "Musterstadt",
    CONF_STREET_ID: 100,
    CONF_STREET_NAME: "Musterstraße",
    CONF_PLZ: "12345",
    CONF_ORTSTEIL: "1a",
}

ENTRY_OPTIONS = {
    CONF_RESTMUELL: RESTMUELL_STANDARD,
    CONF_EXTRA_FRAKTIONEN: [3, 4, 5],
    CONF_SCAN_INTERVAL: 12,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in every test."""
    yield


def _termin(termin_id: int, datum: date, fraktion_id: int) -> Termin:
    return Termin(
        id=termin_id,
        datum=datum,
        fraktion_id=fraktion_id,
        bezirk_id=1000 + fraktion_id,
        bezirk_name="1a",
        info=None,
    )


class FakeAbfallApiClient:
    """In-memory stand-in for the public API client."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create deterministic test data relative to today."""
        self.today = dt_util.now().date()
        self.fail = False
        self.street = Strasse(
            id=100,
            name="Musterstraße",
            plz="12345",
            ortsteil="1a",
            hausnummern=(),
            gueltig_bis=None,
        )
        self.duplicate_street = Strasse(
            id=102,
            name="Musterstraße",
            plz="12346",
            ortsteil="1b",
            hausnummern=(),
            gueltig_bis=None,
        )
        self.streets = [
            self.street,
            self.duplicate_street,
            Strasse(
                id=101,
                name="Musterweg",
                plz="12345",
                ortsteil="1a",
                hausnummern=(),
                gueltig_bis=None,
            ),
        ]
        self.fraktionen = [
            Fraktion(0, "Restmüll", 7, "706E6F"),
            Fraktion(1, "Restmüll 4W rot", 7, "706E6F"),
            Fraktion(2, "Restmüll 4W grün", 7, "706E6F"),
            Fraktion(3, "Biomüll", 10, "9f661f"),
            Fraktion(4, "Altpapier", 11, "2f4a8d"),
            Fraktion(5, "Gelber Sack / Tonne", 4, "f3c70e"),
            Fraktion(6, "Weihnachtsbaum", 14, "66b42c"),
        ]
        self.termine = [
            _termin(1, self.today - timedelta(days=1), 0),
            _termin(2, self.today + timedelta(days=2), 0),
            _termin(3, self.today + timedelta(days=10), 0),
            _termin(4, self.today + timedelta(days=4), 1),
            _termin(5, self.today + timedelta(days=5), 2),
            _termin(6, self.today + timedelta(days=3), 3),
            _termin(7, self.today + timedelta(days=1), 3),
            _termin(8, self.today + timedelta(days=2), 4),
            _termin(9, self.today + timedelta(days=1), 5),
            _termin(10, self.today + timedelta(days=20), 6),
        ]
        self.appdata = AppData(last_import="01.01.2026 00:00:00", db_version=1)

    async def async_get_orte(self) -> list[Ort]:
        """Return one municipality."""
        if self.fail:
            raise AbfallApiConnectionError("down")
        return [Ort(id=1, name="Musterstadt")]

    async def async_get_strassen(self, ort_id: int) -> list[Strasse]:
        """Return test streets."""
        if self.fail:
            raise AbfallApiConnectionError("down")
        return self.streets

    async def async_get_fraktionen(self) -> list[Fraktion]:
        """Return test waste types."""
        if self.fail:
            raise AbfallApiConnectionError("down")
        return self.fraktionen

    async def async_get_strassen_fraktionen(self, strasse_id: int) -> list[Fraktion]:
        """Return test waste types for a street."""
        if self.fail:
            raise AbfallApiConnectionError("down")
        return self.fraktionen

    async def async_get_termine(self, strasse_id: int) -> list[Termin]:
        """Return test collection dates."""
        if self.fail:
            raise AbfallApiConnectionError("down")
        return self.termine

    async def async_get_appdata(self) -> AppData:
        """Return test import metadata."""
        if self.fail:
            raise AbfallApiConnectionError("down")
        return self.appdata


@pytest.fixture
def fake_client(monkeypatch):
    """Patch the API client in setup and config flow."""
    client = FakeAbfallApiClient()
    monkeypatch.setattr(
        "custom_components.abfuhr_awbgl.AbfallApiClient",
        lambda *args, **kwargs: client,
    )
    monkeypatch.setattr(
        "custom_components.abfuhr_awbgl.config_flow.AbfallApiClient",
        lambda *args, **kwargs: client,
    )
    return client


@pytest.fixture
def config_entry(hass) -> MockConfigEntry:
    """Add a config entry to Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        title="Musterstraße (12345)",
    )
    entry.add_to_hass(hass)
    return entry
