from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import (
    IntelliClimaAPIError,
    IntelliClimaEcocomfort2API,
    create_mode_speed_command,
)

pytestmark = pytest.mark.asyncio


async def test_set_token_headers():
    session = MagicMock()
    api = IntelliClimaEcocomfort2API(session, token_headers={"TOKEN": "old"})
    await api.set_token_headers({"TOKEN": "new"})
    assert api._token_headers == {"TOKEN": "new"}


@patch("pyintelliclima.api.REFRESH_DELAY", 0)
@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_mode_speed_ok(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort2API(session, token_headers={"TOKEN": "tok"})

    mock_post.return_value = {"status": "OK"}
    device_sn = "12345678"
    mode = "04"
    speed = "10"

    result = await api.set_mode_speed(device_sn, mode, speed)

    assert result is True
    command = create_mode_speed_command(device_sn, mode, speed)
    mock_post.assert_awaited_once()
    called_args, called_kwargs = mock_post.call_args
    assert called_args[0] is session
    assert called_args[1] == "eco/send/"
    assert called_kwargs["headers"] == {"TOKEN": "tok"}
    assert called_kwargs["json_payload"] == {"trama": command}


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_mode_speed_propagates_request_error(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort2API(session, token_headers={})

    mock_post.side_effect = IntelliClimaAPIError("Got non-OK response status: ERR")

    with pytest.raises(IntelliClimaAPIError, match="non-OK response status"):
        await api.set_mode_speed("12345678", "01", "02")


@patch.object(IntelliClimaEcocomfort2API, "set_mode_speed", new_callable=AsyncMock)
async def test_turn_off_calls_set_mode_speed(mock_set_mode_speed):
    session = MagicMock()
    api = IntelliClimaEcocomfort2API(session, token_headers={})

    mock_set_mode_speed.return_value = True

    result = await api.turn_off("ABCDEF01")

    assert result is True
    mock_set_mode_speed.assert_awaited_once_with("ABCDEF01", mode="0", speed="0")


@patch.object(IntelliClimaEcocomfort2API, "set_mode_speed", new_callable=AsyncMock)
async def test_set_mode_speed_auto_calls_set_mode_speed(mock_set_mode_speed):
    session = MagicMock()
    api = IntelliClimaEcocomfort2API(session, token_headers={})

    mock_set_mode_speed.return_value = True

    result = await api.set_mode_speed_auto("ABCDEF01")

    assert result is True
    mock_set_mode_speed.assert_awaited_once_with("ABCDEF01", mode="4", speed="16")
