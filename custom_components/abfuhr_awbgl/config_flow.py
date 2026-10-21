"""Config and options flow for the AWB Bergisch Gladbach integration."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import AbfallApiClient, AbfallApiError, Fraktion, Ort, Strasse
from .const import (
    CONF_EXTRA_FRAKTIONEN,
    CONF_ORT_ID,
    CONF_ORT_NAME,
    CONF_ORTSTEIL,
    CONF_PLZ,
    CONF_RESTMUELL,
    CONF_SCAN_INTERVAL,
    CONF_STREET,
    CONF_STREET_ID,
    CONF_STREET_NAME,
    DEFAULT_EXTRA_FRAKTIONEN,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    MAX_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
    RESTMUELL_OPTIONS,
    RESTMUELL_STANDARD,
)
from .util import find_street_matches, format_street_label

_RESTMUELL_IDS = frozenset({0, 1, 2})


def _restmuell_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=value, label=label)
                for value, label in RESTMUELL_OPTIONS.items()
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _interval_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL_HOURS,
            max=MAX_SCAN_INTERVAL_HOURS,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement="h",
        )
    )


def _extra_selector(fraktionen: list[Fraktion]) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=str(fraktion.id), label=fraktion.name)
                for fraktion in fraktionen
                if fraktion.id not in _RESTMUELL_IDS
            ],
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
        )
    )


class AbfuhrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AWB Bergisch Gladbach."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._client: AbfallApiClient | None = None
        self._orte: list[Ort] = []
        self._strassen: list[Strasse] = []
        self._selected_ort: Ort | None = None
        self._selected_street: Strasse | None = None
        self._matches: list[Strasse] = []
        self._street_query = ""
        self._plz = ""
        self._available_fraktionen: list[Fraktion] = []
        self._fractions_loaded = False

    def _user_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_STREET, default=self._street_query): (
                    selector.TextSelector()
                ),
                vol.Optional(CONF_PLZ, default=self._plz): selector.TextSelector(),
            }
        )

    def _settings_schema(self) -> vol.Schema:
        extra = [
            fraktion
            for fraktion in self._available_fraktionen
            if fraktion.id not in _RESTMUELL_IDS
        ]
        default_extra = [
            str(fraktion.id)
            for fraktion in extra
            if fraktion.id in DEFAULT_EXTRA_FRAKTIONEN
        ]
        fields: dict[Any, Any] = {
            vol.Required(
                CONF_RESTMUELL,
                default=RESTMUELL_STANDARD,
            ): _restmuell_selector(),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=DEFAULT_SCAN_INTERVAL_HOURS,
            ): _interval_selector(),
        }
        if extra:
            fields[
                vol.Required(
                    CONF_EXTRA_FRAKTIONEN,
                    default=default_extra,
                )
            ] = _extra_selector(extra)
        return vol.Schema(fields)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Ask for the street and postal code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._street_query = str(user_input.get(CONF_STREET, "")).strip()
            self._plz = str(user_input.get(CONF_PLZ, "") or "").strip()

            if not self._street_query:
                errors[CONF_STREET] = "street_required"
            else:
                self._client = AbfallApiClient(async_get_clientsession(self.hass))
                try:
                    self._orte = await self._client.async_get_orte()
                except AbfallApiError:
                    errors["base"] = "cannot_connect"
                else:
                    if not self._orte:
                        return self.async_abort(reason="no_orte")
                    if len(self._orte) > 1:
                        return await self.async_step_ort()
                    self._selected_ort = self._orte[0]
                    result = await self._async_load_streets()
                    if result is not None:
                        return result

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(),
            errors=errors,
        )

    async def async_step_ort(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Select a municipality if the API serves more than one."""
        if user_input is not None:
            ort_id = int(user_input[CONF_ORT_ID])
            self._selected_ort = next(
                (ort for ort in self._orte if ort.id == ort_id),
                None,
            )
            if self._selected_ort is None:
                return self.async_abort(reason="no_orte")
            result = await self._async_load_streets()
            if result is not None:
                return result

        return self.async_show_form(
            step_id="ort",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ORT_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=str(ort.id),
                                    label=ort.name,
                                )
                                for ort in self._orte
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_street_select(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Select a street when the search returned multiple matches."""
        if user_input is not None:
            street_id = int(user_input[CONF_STREET_ID])
            self._selected_street = next(
                (street for street in self._matches if street.id == street_id),
                None,
            )
            if self._selected_street is None:
                return self.async_abort(reason="street_not_found")
            return await self._async_load_fractions_and_show_settings()

        return self.async_show_form(
            step_id="street_select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STREET_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=str(street.id),
                                    label=format_street_label(street),
                                )
                                for street in self._matches
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose waste types and the update interval."""
        if self._selected_street is None or self._selected_ort is None:
            return await self.async_step_user()

        if user_input is not None:
            if not self._fractions_loaded:
                return self.async_show_form(
                    step_id="settings",
                    data_schema=self._settings_schema(),
                    errors={"base": "cannot_connect"},
                )

            restmuell = str(user_input.get(CONF_RESTMUELL, RESTMUELL_STANDARD))
            if restmuell not in RESTMUELL_OPTIONS:
                return self.async_show_form(
                    step_id="settings",
                    data_schema=self._settings_schema(),
                    errors={"base": "invalid_restmuell"},
                )

            extra_values = user_input.get(CONF_EXTRA_FRAKTIONEN, [])
            extra_ids = [int(value) for value in extra_values]
            interval = int(
                user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS)
            )
            interval = max(
                MIN_SCAN_INTERVAL_HOURS,
                min(MAX_SCAN_INTERVAL_HOURS, interval),
            )

            await self.async_set_unique_id(f"{DOMAIN}_{self._selected_street.id}")
            self._abort_if_unique_id_configured()

            title = self._selected_street.name
            if self._selected_street.plz:
                title = f"{title} ({self._selected_street.plz})"

            return self.async_create_entry(
                title=title,
                data={
                    CONF_ORT_ID: self._selected_ort.id,
                    CONF_ORT_NAME: self._selected_ort.name,
                    CONF_STREET_ID: self._selected_street.id,
                    CONF_STREET_NAME: self._selected_street.name,
                    CONF_PLZ: self._selected_street.plz,
                    CONF_ORTSTEIL: self._selected_street.ortsteil,
                },
                options={
                    CONF_RESTMUELL: restmuell,
                    CONF_EXTRA_FRAKTIONEN: extra_ids,
                    CONF_SCAN_INTERVAL: interval,
                },
            )

        return self.async_show_form(
            step_id="settings",
            data_schema=self._settings_schema(),
        )

    async def _async_load_streets(self) -> FlowResult | None:
        """Load streets and continue with selection or settings."""
        if self._client is None or self._selected_ort is None:
            return self.async_abort(reason="no_orte")

        try:
            self._strassen = await self._client.async_get_strassen(
                self._selected_ort.id
            )
        except AbfallApiError:
            return self.async_show_form(
                step_id="user",
                data_schema=self._user_schema(),
                errors={"base": "cannot_connect"},
            )

        if not self._strassen:
            return self.async_abort(reason="no_streets")

        self._matches = find_street_matches(
            self._strassen,
            self._street_query,
            self._plz or None,
        )
        if not self._matches:
            return self.async_show_form(
                step_id="user",
                data_schema=self._user_schema(),
                errors={"base": "street_not_found"},
            )
        if len(self._matches) > 1:
            return await self.async_step_street_select()

        self._selected_street = self._matches[0]
        return await self._async_load_fractions_and_show_settings()

    async def _async_load_fractions_and_show_settings(self) -> FlowResult:
        """Load available waste types and show the settings form."""
        if self._client is None or self._selected_street is None:
            return self.async_abort(reason="street_not_found")

        self._fractions_loaded = False
        try:
            self._available_fraktionen = (
                await self._client.async_get_strassen_fraktionen(
                    self._selected_street.id
                )
            )
        except AbfallApiError:
            return self.async_show_form(
                step_id="settings",
                data_schema=self._settings_schema(),
                errors={"base": "cannot_connect"},
            )

        self._fractions_loaded = True
        return await self.async_step_settings()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return AbfuhrOptionsFlow()


class AbfuhrOptionsFlow(config_entries.OptionsFlow):
    """Change waste types and update interval after setup."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage the integration options."""
        coordinator = self.config_entry.runtime_data.coordinator
        data = coordinator.data
        fraktionen = list(data.fraktionen.values()) if data else []
        extra = [
            fraktion for fraktion in fraktionen if fraktion.id not in _RESTMUELL_IDS
        ]
        current = {**self.config_entry.data, **self.config_entry.options}
        current_extra = [
            str(value)
            for value in current.get(
                CONF_EXTRA_FRAKTIONEN,
                DEFAULT_EXTRA_FRAKTIONEN,
            )
            if int(value) not in _RESTMUELL_IDS
        ]
        available_extra_ids = {str(fraktion.id) for fraktion in extra}
        current_extra = [
            value for value in current_extra if value in available_extra_ids
        ]

        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_RESTMUELL: str(
                        user_input.get(CONF_RESTMUELL, RESTMUELL_STANDARD)
                    ),
                    CONF_EXTRA_FRAKTIONEN: [
                        int(value)
                        for value in user_input.get(
                            CONF_EXTRA_FRAKTIONEN,
                            [],
                        )
                    ],
                    CONF_SCAN_INTERVAL: int(
                        user_input.get(
                            CONF_SCAN_INTERVAL,
                            DEFAULT_SCAN_INTERVAL_HOURS,
                        )
                    ),
                },
            )

        fields: dict[Any, Any] = {
            vol.Required(
                CONF_RESTMUELL,
                default=current.get(CONF_RESTMUELL, RESTMUELL_STANDARD),
            ): _restmuell_selector(),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=current.get(
                    CONF_SCAN_INTERVAL,
                    DEFAULT_SCAN_INTERVAL_HOURS,
                ),
            ): _interval_selector(),
        }
        if extra:
            fields[
                vol.Required(
                    CONF_EXTRA_FRAKTIONEN,
                    default=current_extra,
                )
            ] = _extra_selector(extra)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
        )
