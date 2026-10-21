"""Constants for the AWB Bergisch Gladbach waste collection integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "abfuhr_awbgl"
NAME: Final = "AWB Bergisch Gladbach Abfuhr"
VERSION: Final = "0.1.0"

API_BASE_URL: Final = "https://aw-bgl2-abfallapp.regioit.de/abfall-app-aw-bgl2/rest"
API_TIMEOUT_SECONDS: Final = 15
API_RETRIES: Final = 3
USER_AGENT: Final = f"homeassistant-{DOMAIN}/{VERSION}"

CONF_ORT_ID: Final = "ort_id"
CONF_ORT_NAME: Final = "ort_name"
CONF_STREET: Final = "street"
CONF_STREET_ID: Final = "street_id"
CONF_STREET_NAME: Final = "street_name"
CONF_PLZ: Final = "plz"
CONF_ORTSTEIL: Final = "ortsteil"
CONF_RESTMUELL: Final = "restmuell"
CONF_EXTRA_FRAKTIONEN: Final = "extra_fraktionen"
CONF_SCAN_INTERVAL: Final = "scan_interval"

RESTMUELL_STANDARD: Final = "standard"
RESTMUELL_4W_ROT: Final = "4w-rot"
RESTMUELL_4W_GRUEN: Final = "4w-gruen"
RESTMUELL_ALLE: Final = "alle"

RESTMUELL_OPTIONS: Final[dict[str, str]] = {
    RESTMUELL_STANDARD: "Standard (14-täglich)",
    RESTMUELL_4W_ROT: "4-wöchentlich, rote Tonne",
    RESTMUELL_4W_GRUEN: "4-wöchentlich, grüne Tonne",
    RESTMUELL_ALLE: "Alle Restmüll-Varianten",
}

RESTMUELL_IDS: Final[dict[str, tuple[int, ...]]] = {
    RESTMUELL_STANDARD: (0,),
    RESTMUELL_4W_ROT: (1,),
    RESTMUELL_4W_GRUEN: (2,),
    RESTMUELL_ALLE: (0, 1, 2),
}

DEFAULT_EXTRA_FRAKTIONEN: Final[tuple[int, ...]] = (3, 4, 5)
DEFAULT_SCAN_INTERVAL_HOURS: Final = 12
MIN_SCAN_INTERVAL_HOURS: Final = 1
MAX_SCAN_INTERVAL_HOURS: Final = 48
DEFAULT_UPDATE_INTERVAL: Final = timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS)

FRACTION_ICONS: Final[dict[int, str]] = {
    0: "mdi:trash-can",
    1: "mdi:trash-can",
    2: "mdi:trash-can",
    3: "mdi:leaf",
    4: "mdi:newspaper-variant-outline",
    5: "mdi:recycle",
    6: "mdi:pine-tree",
    7: "mdi:tshirt-crew-outline",
    8: "mdi:biohazard",
}

WEEKDAYS_DE: Final[tuple[str, ...]] = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)
