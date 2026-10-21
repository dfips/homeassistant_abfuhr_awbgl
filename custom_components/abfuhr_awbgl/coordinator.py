"""Data update coordinator for AWB Bergisch Gladbach collection dates."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import (
    AbfallApiClient,
    AbfallApiError,
    AppData,
    Fraktion,
    Strasse,
    Termin,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AbfuhrData:
    """Collection data shared by all entities of a config entry."""

    street: Strasse
    termine: tuple[Termin, ...]
    by_date: dict[date, tuple[Termin, ...]]
    fraktionen: dict[int, Fraktion]
    last_import: str | None
    fetched_at: datetime


class AbfuhrCoordinator(DataUpdateCoordinator[AbfuhrData]):
    """Poll the public AbfallApp API for one street."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AbfallApiClient,
        street: Strasse,
        selected_fraktion_ids: Iterable[int],
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.street = street
        self.selected_fraktion_ids = tuple(selected_fraktion_ids)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{street.id}",
            update_interval=update_interval,
            config_entry=entry,
        )

    async def _async_update_data(self) -> AbfuhrData:
        """Fetch and normalize collection dates."""
        try:
            fraktionen, termine = await asyncio.gather(
                self.client.async_get_fraktionen(),
                self.client.async_get_termine(self.street.id),
            )
        except AbfallApiError as err:
            raise UpdateFailed(str(err)) from err

        appdata: AppData | None
        try:
            appdata = await self.client.async_get_appdata()
        except AbfallApiError:
            appdata = None

        fraktionen_by_id = {fraktion.id: fraktion for fraktion in fraktionen}
        selected_ids = set(self.selected_fraktion_ids)

        filtered: list[Termin] = []
        seen: set[tuple[date, int, int, str | None]] = set()
        for termin in termine:
            if termin.fraktion_id not in selected_ids:
                continue
            key = (
                termin.datum,
                termin.fraktion_id,
                termin.bezirk_id,
                termin.info,
            )
            if key in seen:
                continue
            seen.add(key)
            filtered.append(termin)

        filtered.sort(
            key=lambda item: (
                item.datum,
                item.fraktion_id,
                item.bezirk_name,
            )
        )

        grouped: dict[date, list[Termin]] = {}
        for termin in filtered:
            grouped.setdefault(termin.datum, []).append(termin)

        by_date = {
            datum: tuple(
                sorted(items, key=lambda item: (item.fraktion_id, item.bezirk_name))
            )
            for datum, items in sorted(grouped.items())
        }

        return AbfuhrData(
            street=self.street,
            termine=tuple(filtered),
            by_date=by_date,
            fraktionen=fraktionen_by_id,
            last_import=appdata.last_import if appdata else None,
            fetched_at=dt_util.now(),
        )

    @property
    def today(self) -> date:
        """Return today's date in Home Assistant's timezone."""
        return dt_util.now().date()

    @property
    def next_date(self) -> date | None:
        """Return the next collection date across all selected waste types."""
        if not self.data:
            return None
        future_dates = [datum for datum in self.data.by_date if datum >= self.today]
        return min(future_dates) if future_dates else None

    @property
    def next_by_fraction(self) -> dict[int, date]:
        """Return the next collection date for each selected waste type."""
        result: dict[int, date] = {}
        if not self.data:
            return result
        today = self.today
        for datum, termine in self.data.by_date.items():
            if datum < today:
                continue
            for termin in termine:
                result.setdefault(termin.fraktion_id, datum)
        return result

    def upcoming(self, limit: int = 5) -> list[tuple[date, tuple[Termin, ...]]]:
        """Return the next collection dates, grouped by day."""
        if not self.data:
            return []
        today = self.today
        upcoming = [
            (datum, termine)
            for datum, termine in self.data.by_date.items()
            if datum >= today
        ]
        return upcoming[:limit]

    def fraction_name(self, fraktion_id: int) -> str:
        """Return the API name for a waste type ID."""
        if not self.data:
            return f"Fraktion {fraktion_id}"
        fraktion = self.data.fraktionen.get(fraktion_id)
        return fraktion.name if fraktion else f"Fraktion {fraktion_id}"
