"""Sensor platform for AWB Bergisch Gladbach collection dates."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_RESTMUELL,
    DOMAIN,
    FRACTION_ICONS,
    RESTMUELL_STANDARD,
)
from .coordinator import AbfuhrCoordinator
from .util import weekday_de


class AbfuhrSensorBase(CoordinatorEntity[AbfuhrCoordinator], SensorEntity):
    """Base class for date sensors backed by the coordinator."""

    _attr_attribution = "Daten: AWB Bergisch Gladbach / regio iT"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: AbfuhrCoordinator,
        entry: ConfigEntry,
        unique_suffix: str,
        *,
        name: str | None = None,
        translation_key: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        if name is not None:
            self._attr_name = name
        if translation_key is not None:
            self._attr_translation_key = translation_key
        if icon is not None:
            self._attr_icon = icon
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


class NextCollectionSensor(AbfuhrSensorBase):
    """Sensor for the next collection date across all selected waste types."""

    def __init__(
        self,
        coordinator: AbfuhrCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the next collection sensor."""
        super().__init__(
            coordinator,
            entry,
            "next",
            translation_key="next_collection",
            icon="mdi:trash-can-outline",
        )

    @property
    def native_value(self) -> date | None:
        """Return the next collection date."""
        return self.coordinator.next_date

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return useful details for dashboards and automations."""
        data = self.coordinator.data
        if data is None:
            return {}

        next_date = self.coordinator.next_date
        fractions: list[str] = []
        if next_date is not None:
            fractions = [
                self.coordinator.fraction_name(termin.fraktion_id)
                for termin in data.by_date.get(next_date, ())
            ]

        next_dates = [
            {
                "date": datum.isoformat(),
                "weekday": weekday_de(datum),
                "fractions": [
                    self.coordinator.fraction_name(termin.fraktion_id)
                    for termin in termine
                ],
            }
            for datum, termine in self.coordinator.upcoming(5)
        ]

        return {
            "days_until": (
                (next_date - self.coordinator.today).days
                if next_date is not None
                else None
            ),
            "weekday": weekday_de(next_date) if next_date is not None else None,
            "fractions": fractions,
            "next_dates": next_dates,
            "street": data.street.name,
            "plz": data.street.plz,
            "ortsteil": data.street.ortsteil,
            "last_import": data.last_import,
            "restmuell_variante": self._entry.options.get(
                CONF_RESTMUELL,
                RESTMUELL_STANDARD,
            ),
        }


class FractionSensor(AbfuhrSensorBase):
    """Sensor for the next collection date of one waste type."""

    def __init__(
        self,
        coordinator: AbfuhrCoordinator,
        entry: ConfigEntry,
        fraktion_id: int,
        name: str,
    ) -> None:
        """Initialize the waste type sensor."""
        super().__init__(
            coordinator,
            entry,
            f"fraction_{fraktion_id}",
            name=name,
            icon=FRACTION_ICONS.get(fraktion_id, "mdi:trash-can-outline"),
        )
        self._fraktion_id = fraktion_id
        self._fraktion_name = name

    @property
    def native_value(self) -> date | None:
        """Return the next collection date for this waste type."""
        return self.coordinator.next_by_fraction.get(self._fraktion_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details for this waste type."""
        data = self.coordinator.data
        if data is None:
            return {}
        next_date = self.coordinator.next_by_fraction.get(self._fraktion_id)
        return {
            "fraktion_id": self._fraktion_id,
            "fraktion": self._fraktion_name,
            "days_until": (
                (next_date - self.coordinator.today).days
                if next_date is not None
                else None
            ),
            "weekday": weekday_de(next_date) if next_date is not None else None,
            "street": data.street.name,
            "last_import": data.last_import,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors for a config entry."""
    coordinator: AbfuhrCoordinator = entry.runtime_data.coordinator
    if coordinator.data is None:
        return

    entities: list[SensorEntity] = [
        NextCollectionSensor(coordinator, entry),
    ]
    for fraktion_id in coordinator.selected_fraktion_ids:
        fraktion = coordinator.data.fraktionen.get(fraktion_id)
        if fraktion is None:
            continue
        entities.append(
            FractionSensor(
                coordinator,
                entry,
                fraktion_id,
                fraktion.name,
            )
        )

    async_add_entities(entities)
