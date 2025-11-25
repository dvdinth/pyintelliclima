from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import (
    IntelliClimaAPIError,
    IntelliClimaEcocomfortAPI,
    create_mode_speed_command,
)

pytestmark = pytest.mark.asyncio


async def test_set_token_headers():
    session = MagicMock()
    api = IntelliClimaEcocomfortAPI(session, token_headers={"TOKEN": "old"})
    await api.set_token_headers({"TOKEN": "new"})
    assert api._token_headers == {"TOKEN": "new"}


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_mode_speed_ok(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfortAPI(session, token_headers={"TOKEN": "tok"})

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
async def test_set_mode_speed_error_status_raises(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfortAPI(session, token_headers={})

    mock_post.return_value = {"status": "ERR"}

    with pytest.raises(IntelliClimaAPIError):
        await api.set_mode_speed("12345678", "01", "02")


@patch.object(IntelliClimaEcocomfortAPI, "set_mode_speed", new_callable=AsyncMock)
async def test_turn_off_calls_set_mode_speed(mock_set_mode_speed):
    session = MagicMock()
    api = IntelliClimaEcocomfortAPI(session, token_headers={})

    mock_set_mode_speed.return_value = True

    result = await api.turn_off("ABCDEF01")

    assert result is True
    mock_set_mode_speed.assert_awaited_once_with("ABCDEF01", mode="00", speed="00")
