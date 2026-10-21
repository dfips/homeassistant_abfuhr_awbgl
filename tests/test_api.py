"""Tests for API parsing and street matching helpers."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.abfuhr_awbgl.api import (
    AbfallApiDataError,
    Strasse,
    _parse_fraktion,
    _parse_strasse,
    _parse_termin,
)
from custom_components.abfuhr_awbgl.const import (
    RESTMUELL_ALLE,
    RESTMUELL_STANDARD,
)
from custom_components.abfuhr_awbgl.util import (
    find_street_matches,
    normalize_street_name,
    selected_fraction_ids,
)


def _street(
    street_id: int,
    name: str,
    plz: str = "12345",
    ortsteil: str = "1a",
) -> Strasse:
    return Strasse(
        id=street_id,
        name=name,
        plz=plz,
        ortsteil=ortsteil,
        hausnummern=(),
        gueltig_bis=None,
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Musterstraße", "musterstrasse"),
        ("Musterstrasse", "musterstrasse"),
        ("Musterstr.", "musterstrasse"),
        ("Musterstr", "musterstrasse"),
        ("Große Straße", "grosse strasse"),
        ("Müllerweg", "muellerweg"),
        ("  Haupt-Str.  ", "haupt strasse"),
    ],
)
def test_normalize_street_name(value: str, expected: str) -> None:
    """Street names are normalized for German spelling variants."""
    assert normalize_street_name(value) == expected


def test_find_street_matches_exact() -> None:
    """An exact match wins over substring matches."""
    streets = [_street(1, "Musterstraße"), _street(2, "Musterstraße Nord")]
    assert [street.id for street in find_street_matches(streets, "Musterstraße")] == [1]


def test_find_street_matches_plz() -> None:
    """The postal code narrows down duplicate street names."""
    streets = [
        _street(1, "Musterstraße", "12345"),
        _street(2, "Musterstraße", "12346"),
    ]
    matches = find_street_matches(streets, "Musterstraße", "12346")
    assert [street.id for street in matches] == [2]


def test_find_street_matches_typo() -> None:
    """A small typo still produces a suggestion."""
    streets = [_street(1, "Musterstraße")]
    matches = find_street_matches(streets, "Musterstrase")
    assert [street.id for street in matches] == [1]


def test_find_street_matches_substring() -> None:
    """A partial name matches streets containing it."""
    streets = [_street(1, "Musterweg"), _street(2, "Am Musterweg")]
    assert {street.id for street in find_street_matches(streets, "weg")} == {1, 2}


def test_find_street_matches_empty() -> None:
    """An empty query returns nothing."""
    assert find_street_matches([_street(1, "Musterweg")], "   ") == []


def test_selected_fraction_ids_standard() -> None:
    """The standard residual waste variant is combined with extras."""
    assert selected_fraction_ids(RESTMUELL_STANDARD, [3, 4, 5]) == (0, 3, 4, 5)


def test_selected_fraction_ids_all_variants() -> None:
    """All residual waste variants are included once."""
    assert selected_fraction_ids(RESTMUELL_ALLE, [3, 0, 3]) == (0, 1, 2, 3)


def test_parse_strasse() -> None:
    """Street payloads are parsed into typed objects."""
    street = _parse_strasse(
        {
            "id": 100,
            "name": "Musterstraße",
            "plz": "12345",
            "ortsteilName": "1a",
            "gueltigBis": None,
            "hausNrList": [
                {
                    "id": 200,
                    "nr": "1",
                    "plz": "12345",
                    "staticId": "abc",
                }
            ],
        }
    )
    assert street.id == 100
    assert street.name == "Musterstraße"
    assert street.hausnummern[0].nr == "1"


def test_parse_fraktion() -> None:
    """Waste type payloads are parsed into typed objects."""
    fraktion = _parse_fraktion(
        {"id": 3, "name": "Biomüll", "iconNr": 10, "farbeRgb": "9f661f"}
    )
    assert fraktion.id == 3
    assert fraktion.name == "Biomüll"
    assert fraktion.icon_nr == 10


def test_parse_termin() -> None:
    """Collection payloads are parsed into typed objects."""
    termin = _parse_termin(
        {
            "id": 300,
            "datum": "2026-10-26",
            "info": None,
            "bezirk": {
                "id": 400,
                "name": "1a",
                "fraktionId": 3,
            },
        }
    )
    assert termin.datum == date(2026, 10, 26)
    assert termin.fraktion_id == 3
    assert termin.bezirk_id == 400


def test_parse_termin_invalid_date() -> None:
    """Invalid dates raise a data error."""
    with pytest.raises(AbfallApiDataError):
        _parse_termin(
            {
                "id": 300,
                "datum": "not-a-date",
                "bezirk": {"id": 400, "fraktionId": 3},
            }
        )
