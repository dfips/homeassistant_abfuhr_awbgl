"""Calendar platform for AWB Bergisch Gladbach collection dates."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Termin
from .const import DOMAIN
from .coordinator import AbfuhrCoordinator


class AbfuhrCalendar(CoordinatorEntity[AbfuhrCoordinator], CalendarEntity):
    """Calendar with one all-day event per collection day."""

    _attr_attribution = "Daten: AWB Bergisch Gladbach / regio iT"
    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-month"
    _attr_translation_key = "collection"

    def __init__(
        self,
        coordinator: AbfuhrCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="AWB Bergisch Gladbach",
            model="Abfuhrkalender",
        )

    @property
    def available(self) -> bool:
        """Return whether the coordinator has data."""
        return super().available and self.coordinator.data is not None

    def _event_for(
        self,
        datum: date,
        termine: tuple[Termin, ...],
    ) -> CalendarEvent:
        """Build an all-day calendar event for one collection day."""
        data = self.coordinator.data
        street = data.street if data else self.coordinator.street
        fractions = [
            self.coordinator.fraction_name(termin.fraktion_id) for termin in termine
        ]
        summary = "Abfuhr: " + ", ".join(fractions)
        location_parts = [street.name]
        if street.plz:
            location_parts.append(street.plz)
        return CalendarEvent(
            start=datum,
            end=datum + timedelta(days=1),
            summary=summary,
            description=(
                f"Abfuhrtermine für {street.name}"
                + (f" ({street.plz})" if street.plz else "")
            ),
            location=", ".join(location_parts),
            uid=f"{self._entry.entry_id}-{datum.isoformat()}",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return today's or the next collection event."""
        data = self.coordinator.data
        if data is None:
            return None
        today = self.coordinator.today
        for datum, termine in data.by_date.items():
            if datum >= today:
                return self._event_for(datum, termine)
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return collection events in the requested range."""
        data = self.coordinator.data
        if data is None:
            return []

        start = start_date.date() if isinstance(start_date, datetime) else start_date
        end = end_date.date() if isinstance(end_date, datetime) else end_date

        return [
            self._event_for(datum, termine)
            for datum, termine in data.by_date.items()
            if start <= datum < end
        ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar for a config entry."""
    coordinator: AbfuhrCoordinator = entry.runtime_data.coordinator
    async_add_entities([AbfuhrCalendar(coordinator, entry)])
