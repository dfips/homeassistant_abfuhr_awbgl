"""Tests for the data update coordinator."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.abfuhr_awbgl.const import DOMAIN
from custom_components.abfuhr_awbgl.coordinator import AbfuhrCoordinator

from .conftest import ENTRY_DATA, ENTRY_OPTIONS


async def test_coordinator_filters_and_sorts(hass, fake_client) -> None:
    """Only selected waste types are kept and dates are sorted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        title="Musterstraße (12345)",
    )
    entry.add_to_hass(hass)

    coordinator = AbfuhrCoordinator(
        hass,
        entry,
        fake_client,
        fake_client.street,
        (0, 3, 4, 5),
        timedelta(hours=12),
    )
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data is not None
    assert coordinator.next_date == fake_client.today + timedelta(days=1)
    assert list(coordinator.data.by_date) == sorted(coordinator.data.by_date)
    assert coordinator.next_by_fraction == {
        0: fake_client.today + timedelta(days=2),
        3: fake_client.today + timedelta(days=1),
        4: fake_client.today + timedelta(days=2),
        5: fake_client.today + timedelta(days=1),
    }
    assert coordinator.fraction_name(3) == "Biomüll"
    assert coordinator.fraction_name(99) == "Fraktion 99"

    upcoming = coordinator.upcoming(2)
    assert [datum for datum, _ in upcoming] == [
        fake_client.today + timedelta(days=1),
        fake_client.today + timedelta(days=2),
    ]

    # Past dates are kept in the data but never reported as upcoming.
    assert fake_client.today - timedelta(days=1) in coordinator.data.by_date
    assert fake_client.today - timedelta(days=1) not in [datum for datum, _ in upcoming]


async def test_coordinator_all_restmuell_variants(hass, fake_client) -> None:
    """All residual waste variants produce individual next dates."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        title="Musterstraße (12345)",
    )
    entry.add_to_hass(hass)

    coordinator = AbfuhrCoordinator(
        hass,
        entry,
        fake_client,
        fake_client.street,
        (0, 1, 2, 3),
        timedelta(hours=12),
    )
    await coordinator.async_refresh()

    assert coordinator.next_by_fraction == {
        0: fake_client.today + timedelta(days=2),
        1: fake_client.today + timedelta(days=4),
        2: fake_client.today + timedelta(days=5),
        3: fake_client.today + timedelta(days=1),
    }


async def test_coordinator_api_failure(hass, fake_client) -> None:
    """API errors are converted into UpdateFailed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
        title="Musterstraße (12345)",
    )
    entry.add_to_hass(hass)

    coordinator = AbfuhrCoordinator(
        hass,
        entry,
        fake_client,
        fake_client.street,
        (0, 3, 4, 5),
        timedelta(hours=12),
    )
    fake_client.fail = True

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
