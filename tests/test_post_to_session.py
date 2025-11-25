import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError

from pyintelliclima.api import IntelliClimaAPIError, generate_read_url, post_to_session

pytestmark = pytest.mark.asyncio


async def test_post_to_session_ok(monkeypatch):
    session = MagicMock()
    response = AsyncMock()
    response.text.return_value = json.dumps({"status": "OK", "foo": "bar"})
    response.raise_for_status.return_value = None
    session.post.return_value.__aenter__.return_value = response

    result = await post_to_session(session, "some/path", headers={"X": "Y"}, json_payload={"a": 1})

    session.post.assert_called_once_with(
        generate_read_url("some/path"),
        headers={"X": "Y"},
        json={"a": 1},
    )
    assert result == {"status": "OK", "foo": "bar"}


async def test_post_to_session_non_ok_status(monkeypatch):
    session = MagicMock()
    response = AsyncMock()
    response.text.return_value = json.dumps({"status": "ERR", "msg": "nope"})
    response.raise_for_status.return_value = None
    session.post.return_value.__aenter__.return_value = response

    with pytest.raises(IntelliClimaAPIError):
        await post_to_session(session, "some/path")


async def test_post_to_session_http_error():
    session = MagicMock()

    # Make the async context manager itself raise ClientError
    cm = AsyncMock()
    cm.__aenter__.side_effect = ClientError("boom")
    session.post.return_value = cm

    with pytest.raises(ClientError):
        await post_to_session(session, "another/path")

    session.post.assert_called_once_with(
        generate_read_url("another/path"),
        headers=None,
        json=None,
    )
