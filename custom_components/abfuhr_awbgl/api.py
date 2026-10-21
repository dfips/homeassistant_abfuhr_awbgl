"""Async client for the public AbfallApp API used by AWB Bergisch Gladbach."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
import json
import logging
from typing import Any, Final

import aiohttp

from .const import (
    API_BASE_URL,
    API_RETRIES,
    API_TIMEOUT_SECONDS,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

_JSON_HEADERS: Final = {
    "Accept": "application/json",
    "User-Agent": USER_AGENT,
}


class AbfallApiError(Exception):
    """Base class for errors raised by the AbfallApp client."""


class AbfallApiConnectionError(AbfallApiError):
    """Raised when the API cannot be reached."""


class AbfallApiNotFoundError(AbfallApiError):
    """Raised when a requested resource does not exist."""


class AbfallApiDataError(AbfallApiError):
    """Raised when the API returns an unexpected payload."""


@dataclass(frozen=True, slots=True)
class Ort:
    """A municipality served by the API."""

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class Hausnummer:
    """A house number belonging to a street."""

    id: int
    nr: str
    plz: str | None
    static_id: str | None


@dataclass(frozen=True, slots=True)
class Strasse:
    """A street in a municipality."""

    id: int
    name: str
    plz: str | None
    ortsteil: str | None
    hausnummern: tuple[Hausnummer, ...]
    gueltig_bis: str | None


@dataclass(frozen=True, slots=True)
class Fraktion:
    """A waste type such as residual waste or paper."""

    id: int
    name: str
    icon_nr: int | None
    farbe_rgb: str | None


@dataclass(frozen=True, slots=True)
class Termin:
    """A single collection date for one waste type."""

    id: int
    datum: date
    fraktion_id: int
    bezirk_id: int
    bezirk_name: str
    info: str | None


@dataclass(frozen=True, slots=True)
class AppData:
    """Metadata reported by the API."""

    last_import: str | None
    db_version: int | None


def _as_int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as err:
        raise AbfallApiDataError(f"Invalid integer in field {field!r}") from err


def _as_optional_int(value: Any, field: str) -> int | None:
    if value is None:
        return None
    return _as_int(value, field)


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as err:
        raise AbfallApiDataError(f"Invalid date in field {field!r}") from err


def _expect_list(payload: Any, endpoint: str) -> list[Any]:
    if not isinstance(payload, list):
        raise AbfallApiDataError(f"Expected a list from {endpoint}")
    return payload


def _parse_ort(payload: Any) -> Ort:
    if not isinstance(payload, dict):
        raise AbfallApiDataError("Invalid Ort payload")
    return Ort(
        id=_as_int(payload.get("id"), "Ort.id"),
        name=str(payload.get("name") or ""),
    )


def _parse_hausnummer(payload: Any) -> Hausnummer:
    if not isinstance(payload, dict):
        raise AbfallApiDataError("Invalid Hausnummer payload")
    return Hausnummer(
        id=_as_int(payload.get("id"), "Hausnummer.id"),
        nr=str(payload.get("nr") or ""),
        plz=_as_optional_str(payload.get("plz")),
        static_id=_as_optional_str(payload.get("staticId")),
    )


def _parse_strasse(payload: Any) -> Strasse:
    if not isinstance(payload, dict):
        raise AbfallApiDataError("Invalid Strasse payload")
    hausnummern_payload = payload.get("hausNrList") or []
    if not isinstance(hausnummern_payload, list):
        raise AbfallApiDataError("Invalid hausNrList payload")
    return Strasse(
        id=_as_int(payload.get("id"), "Strasse.id"),
        name=str(payload.get("name") or ""),
        plz=_as_optional_str(payload.get("plz")),
        ortsteil=_as_optional_str(payload.get("ortsteilName")),
        hausnummern=tuple(_parse_hausnummer(item) for item in hausnummern_payload),
        gueltig_bis=_as_optional_str(payload.get("gueltigBis")),
    )


def _parse_fraktion(payload: Any) -> Fraktion:
    if not isinstance(payload, dict):
        raise AbfallApiDataError("Invalid Fraktion payload")
    return Fraktion(
        id=_as_int(payload.get("id"), "Fraktion.id"),
        name=str(payload.get("name") or ""),
        icon_nr=_as_optional_int(payload.get("iconNr"), "Fraktion.iconNr"),
        farbe_rgb=_as_optional_str(payload.get("farbeRgb")),
    )


def _parse_termin(payload: Any) -> Termin:
    if not isinstance(payload, dict):
        raise AbfallApiDataError("Invalid Termin payload")
    bezirk = payload.get("bezirk")
    if not isinstance(bezirk, dict):
        raise AbfallApiDataError("Invalid Termin.bezirk payload")
    return Termin(
        id=_as_int(payload.get("id"), "Termin.id"),
        datum=_as_date(payload.get("datum"), "Termin.datum"),
        fraktion_id=_as_int(bezirk.get("fraktionId"), "Termin.bezirk.fraktionId"),
        bezirk_id=_as_int(bezirk.get("id"), "Termin.bezirk.id"),
        bezirk_name=str(bezirk.get("name") or ""),
        info=_as_optional_str(payload.get("info")),
    )


class AbfallApiClient:
    """Small async client for the public regio iT AbfallApp endpoints."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str = API_BASE_URL,
    ) -> None:
        """Initialize the client with a Home Assistant managed session."""
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def _async_request(self, path: str) -> Any:
        url = f"{self._base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(API_RETRIES):
            try:
                async with asyncio.timeout(API_TIMEOUT_SECONDS):
                    async with self._session.get(
                        url, headers=_JSON_HEADERS
                    ) as response:
                        if response.status == 404:
                            raise AbfallApiNotFoundError(f"Resource not found: {path}")
                        if response.status == 429 or response.status >= 500:
                            last_error = AbfallApiConnectionError(
                                f"HTTP {response.status} from {path}"
                            )
                        elif response.status >= 400:
                            raise AbfallApiError(f"HTTP {response.status} from {path}")
                        else:
                            try:
                                return await response.json(content_type=None)
                            except (
                                aiohttp.ContentTypeError,
                                json.JSONDecodeError,
                            ) as err:
                                raise AbfallApiDataError(
                                    f"Invalid JSON from {path}"
                                ) from err
            except AbfallApiNotFoundError, AbfallApiDataError, AbfallApiError:
                raise
            except (TimeoutError, aiohttp.ClientError) as err:
                last_error = err

            if attempt < API_RETRIES - 1:
                await asyncio.sleep(2**attempt)

        raise AbfallApiConnectionError(f"Could not reach {path}") from last_error

    async def async_get_orte(self) -> list[Ort]:
        """Return all municipalities served by this API."""
        payload = await self._async_request("/orte")
        return [_parse_ort(item) for item in _expect_list(payload, "/orte")]

    async def async_get_strassen(self, ort_id: int) -> list[Strasse]:
        """Return all streets for a municipality."""
        payload = await self._async_request(f"/orte/{ort_id}/strassen")
        return [
            _parse_strasse(item)
            for item in _expect_list(payload, f"/orte/{ort_id}/strassen")
        ]

    async def async_get_fraktionen(self) -> list[Fraktion]:
        """Return all waste types known to the API."""
        payload = await self._async_request("/fraktionen")
        return [_parse_fraktion(item) for item in _expect_list(payload, "/fraktionen")]

    async def async_get_strassen_fraktionen(self, strasse_id: int) -> list[Fraktion]:
        """Return the waste types available for a street."""
        payload = await self._async_request(f"/strassen/{strasse_id}/fraktionen")
        return [
            _parse_fraktion(item)
            for item in _expect_list(payload, f"/strassen/{strasse_id}/fraktionen")
        ]

    async def async_get_termine(self, strasse_id: int) -> list[Termin]:
        """Return all collection dates for a street."""
        payload = await self._async_request(f"/strassen/{strasse_id}/termine")
        return [
            _parse_termin(item)
            for item in _expect_list(payload, f"/strassen/{strasse_id}/termine")
        ]

    async def async_get_appdata(self) -> AppData:
        """Return import metadata from the API."""
        payload = await self._async_request("/appdata")
        if not isinstance(payload, dict):
            raise AbfallApiDataError("Invalid appdata payload")
        return AppData(
            last_import=_as_optional_str(payload.get("lastImport")),
            db_version=_as_optional_int(payload.get("dbversion"), "appdata.dbversion"),
        )
