"""Tests for the calendar entity."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.abfuhr_awbgl.const import DOMAIN


async def test_calendar_events(hass, fake_client, config_entry) -> None:
    """The calendar exposes all upcoming collection days."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    calendar_id = registry.async_get_entity_id(
        "calendar",
        DOMAIN,
        f"{config_entry.entry_id}_calendar",
    )
    assert calendar_id is not None

    entity = hass.data["calendar"].get_entity(calendar_id)
    assert entity is not None

    event = entity.event
    assert event is not None
    assert event.start == fake_client.today + timedelta(days=1)
    assert event.end == fake_client.today + timedelta(days=2)
    assert "Biomüll" in event.summary
    assert "Gelber Sack / Tonne" in event.summary

    start = datetime.combine(fake_client.today, time.min, tzinfo=dt_util.UTC)
    end = start + timedelta(days=7)
    events = await entity.async_get_events(hass, start, end)

    assert [
        calendar_event.start.date()
        if isinstance(calendar_event.start, datetime)
        else calendar_event.start
        for calendar_event in events
    ] == [
        fake_client.today + timedelta(days=1),
        fake_client.today + timedelta(days=2),
        fake_client.today + timedelta(days=3),
    ]
    assert all(
        (
            calendar_event.end.date()
            if isinstance(calendar_event.end, datetime)
            else calendar_event.end
        )
        == (
            calendar_event.start.date()
            if isinstance(calendar_event.start, datetime)
            else calendar_event.start
        )
        + timedelta(days=1)
        for calendar_event in events
    )
