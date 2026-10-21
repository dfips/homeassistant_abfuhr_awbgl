"""Helpers for street matching and waste type selection."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
import difflib
import re

from .api import Strasse
from .const import (
    RESTMUELL_IDS,
    RESTMUELL_STANDARD,
    WEEKDAYS_DE,
)

_UMLAUTS = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "ae",
        "Ö": "oe",
        "Ü": "ue",
    }
)


def normalize_street_name(value: str) -> str:
    """Normalize a German street name for comparisons."""
    normalized = value.casefold().strip().replace("ß", "ss").translate(_UMLAUTS)
    normalized = re.sub(r"str\.?(?=\s|$)", "strasse", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def find_street_matches(
    streets: Iterable[Strasse],
    query: str,
    plz: str | None = None,
) -> list[Strasse]:
    """Return streets matching a user supplied name and optional postal code."""
    query_normalized = normalize_street_name(query)
    if not query_normalized:
        return []

    candidates = list(streets)
    if plz and plz.strip():
        plz_normalized = plz.strip()
        candidates = [
            street
            for street in candidates
            if (street.plz or "").strip() == plz_normalized
        ]

    exact = [
        street
        for street in candidates
        if normalize_street_name(street.name) == query_normalized
    ]
    if exact:
        return exact

    starts_with = [
        street
        for street in candidates
        if normalize_street_name(street.name).startswith(query_normalized)
    ]
    if starts_with:
        return starts_with

    contains = [
        street
        for street in candidates
        if query_normalized in normalize_street_name(street.name)
    ]
    if contains:
        return contains

    normalized_names = {
        normalize_street_name(street.name): street for street in candidates
    }
    close_names = difflib.get_close_matches(
        query_normalized,
        list(normalized_names),
        n=5,
        cutoff=0.75,
    )
    return [normalized_names[name] for name in close_names if name in normalized_names]


def format_street_label(street: Strasse) -> str:
    """Return a compact label for config flow selection lists."""
    parts = [street.name]
    if street.plz:
        parts.append(street.plz)
    if street.ortsteil:
        parts.append(f"Ortsteil {street.ortsteil}")
    return " · ".join(parts)


def selected_fraction_ids(
    restmuell: str,
    extra_fraktionen: Iterable[int],
) -> tuple[int, ...]:
    """Return the ordered, de-duplicated set of selected waste type IDs."""
    restmuell_ids = RESTMUELL_IDS.get(restmuell, RESTMUELL_IDS[RESTMUELL_STANDARD])
    selected = list(restmuell_ids)
    for fraktion_id in extra_fraktionen:
        if fraktion_id not in selected:
            selected.append(fraktion_id)
    return tuple(selected)


def weekday_de(value: date) -> str:
    """Return the German weekday name for a date."""
    return WEEKDAYS_DE[value.weekday()]
