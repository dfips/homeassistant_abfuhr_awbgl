"""Tests for the HTTP client without network access."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.abfuhr_awbgl.api import (
    AbfallApiClient,
    AbfallApiConnectionError,
    AbfallApiDataError,
    AbfallApiNotFoundError,
)


class FakeResponse:
    """Minimal async context manager response."""

    def __init__(self, status: int, payload: Any = None) -> None:
        """Initialize the fake response."""
        self.status = status
        self.payload = payload

    async def __aenter__(self) -> FakeResponse:
        """Enter the async context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the async context."""
        return

    async def json(self, content_type: str | None = None) -> Any:
        """Return the queued payload."""
        return self.payload


class FakeSession:
    """Minimal session that returns queued responses."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        """Initialize the fake session."""
        self.responses = list(responses)
        self.urls: list[str] = []

    def get(self, url: str, headers: dict[str, str] | None = None) -> FakeResponse:
        """Return the next queued response."""
        self.urls.append(url)
        return self.responses.pop(0)


async def test_client_parses_orte() -> None:
    """The client builds the expected URL and parses the payload."""
    session = FakeSession([FakeResponse(200, [{"id": 1, "name": "Musterstadt"}])])
    client = AbfallApiClient(session, base_url="https://example.invalid/rest")

    orte = await client.async_get_orte()

    assert [(ort.id, ort.name) for ort in orte] == [(1, "Musterstadt")]
    assert session.urls == ["https://example.invalid/rest/orte"]


async def test_client_retries_server_errors() -> None:
    """A 5xx response is retried."""
    session = FakeSession([FakeResponse(500), FakeResponse(200, [])])
    client = AbfallApiClient(session, base_url="https://example.invalid/rest")

    with patch(
        "custom_components.abfuhr_awbgl.api.asyncio.sleep",
        new=AsyncMock(),
    ):
        orte = await client.async_get_orte()

    assert orte == []
    assert len(session.urls) == 2


async def test_client_gives_up_after_server_errors() -> None:
    """Repeated 5xx responses raise a connection error."""
    session = FakeSession([FakeResponse(500), FakeResponse(500), FakeResponse(500)])
    client = AbfallApiClient(session, base_url="https://example.invalid/rest")

    with (
        patch(
            "custom_components.abfuhr_awbgl.api.asyncio.sleep",
            new=AsyncMock(),
        ),
        pytest.raises(AbfallApiConnectionError),
    ):
        await client.async_get_orte()


async def test_client_does_not_retry_not_found() -> None:
    """A 404 is surfaced immediately."""
    session = FakeSession([FakeResponse(404)])
    client = AbfallApiClient(session, base_url="https://example.invalid/rest")

    with pytest.raises(AbfallApiNotFoundError):
        await client.async_get_termine(1)

    assert len(session.urls) == 1


async def test_client_rejects_invalid_json() -> None:
    """Invalid JSON raises a data error."""
    response = FakeResponse(200)
    response.json = AsyncMock(  # type: ignore[method-assign]
        side_effect=json.JSONDecodeError("broken", "", 0)
    )
    session = FakeSession([response])
    client = AbfallApiClient(session, base_url="https://example.invalid/rest")

    with pytest.raises(AbfallApiDataError):
        await client.async_get_orte()
