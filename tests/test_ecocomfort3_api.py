from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import (
    IntelliClimaAPI,
    IntelliClimaEcocomfort3API,
    create_season_free_cooling_command,
)
from pyintelliclima.const import (
    FanMode,
    FanSpeed,
    FreeCoolingLevel,
    Season,
    ThresholdLevel,
    SlaveRotation,
)

pytestmark = pytest.mark.asyncio


async def test_set_token_headers():
    api = IntelliClimaEcocomfort3API(MagicMock(), token_headers={"TOKEN": "old"})

    await api.set_token_headers({"TOKEN": "new"})

    assert api._token_headers == {"TOKEN": "new"}


@patch("pyintelliclima.api.REFRESH_DELAY", 0)
@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_mode_speed_uses_eco3_endpoint(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort3API(session, token_headers={"TOKEN": "tok"})
    mock_post.return_value = {"status": "OK"}

    result = await api.set_mode_speed("AABBCCDD", FanMode.alternate, FanSpeed.high)

    assert result is True
    mock_post.assert_awaited_once_with(
        session,
        "eco3/send/",
        headers={"TOKEN": "tok"},
        json_payload={"trama": "0AAABBCCDD000E2F005000000304620D"},
    )


@patch.object(IntelliClimaEcocomfort3API, "set_mode_speed", new_callable=AsyncMock)
async def test_turn_off(mock_set_mode_speed):
    api = IntelliClimaEcocomfort3API(MagicMock(), token_headers={})
    mock_set_mode_speed.return_value = True

    assert await api.turn_off("AABBCCDD") is True
    mock_set_mode_speed.assert_awaited_once_with("AABBCCDD", mode=FanMode.off, speed=FanSpeed.off)


@patch.object(IntelliClimaEcocomfort3API, "set_mode_speed", new_callable=AsyncMock)
async def test_set_mode_speed_auto(mock_set_mode_speed):
    api = IntelliClimaEcocomfort3API(MagicMock(), token_headers={})
    mock_set_mode_speed.return_value = True

    assert await api.set_mode_speed_auto("AABBCCDD") is True
    mock_set_mode_speed.assert_awaited_once_with(
        "AABBCCDD", mode=FanMode.sensor, speed=FanSpeed.auto_set
    )


async def test_main_api_updates_eco3_token_headers():
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")

    await api.set_all_token_headers({"TOKENID": "1", "TOKEN": "new"})

    assert api.ecocomfort3._token_headers == {"TOKENID": "1", "TOKEN": "new"}


async def test_create_eco3_season_command():
    assert (
        create_season_free_cooling_command("AABBCCDD", season=Season.summer)
        == "0AAABBCCDD00182F002000007F7F7F7F1F7F000000000000F50D"
    )


async def test_create_eco3_free_cooling_command():
    assert (
        create_season_free_cooling_command("AABBCCDD", free_cooling=FreeCoolingLevel.low)
        == "0AAABBCCDD00182F002000007F7F7F7F717F000000000000910D"
    )


@patch("pyintelliclima.api.REFRESH_DELAY", 0)
@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_offsets_uses_eco3_endpoint(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort3API(session, token_headers={"TOKEN": "tok"})
    mock_post.return_value = {"status": "OK"}

    assert await api.set_temperature_and_humidity_offsets("AABBCCDD", -5.0, 1)

    mock_post.assert_awaited_once_with(
        session,
        "eco3/send/",
        headers={"TOKEN": "tok"},
        json_payload={"trama": "0AAABBCCDD00102F00210000FE0C0064BD0D"},
    )


@patch("pyintelliclima.api.REFRESH_DELAY", 0)
@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_thresholds_uses_eco3_co2_field(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort3API(session, token_headers={"TOKEN": "tok"})
    mock_post.return_value = {"status": "OK"}

    assert await api.set_advanced_settings(
        "AABBCCDD",
        humidity_threshold=ThresholdLevel.low,
        co2_threshold=ThresholdLevel.medium,
        co2_threshold_advanced=True,
        lux_threshold=ThresholdLevel.high,
    )

    mock_post.assert_awaited_once_with(
        session,
        "eco3/send/",
        headers={"TOKEN": "tok"},
        json_payload={"trama": "0AAABBCCDD00182F002000007F0103827F7F000000000000C90D"},
    )


@patch.object(IntelliClimaEcocomfort3API, "set_advanced_settings", new_callable=AsyncMock)
async def test_set_slave_rotation_calls_set_advanced_settings(mock_set_advanced):
    api = IntelliClimaEcocomfort3API(MagicMock(), token_headers={})
    mock_set_advanced.return_value = True

    assert await api.set_slave_rotation("AABBCCDD", SlaveRotation.discordant)

    mock_set_advanced.assert_awaited_once_with(
        "AABBCCDD", slave_rotation=SlaveRotation.discordant
    )


@patch("pyintelliclima.api.REFRESH_DELAY", 0)
@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_season_updates_device_and_server_state(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort3API(session, token_headers={"TOKEN": "tok"})
    mock_post.return_value = {"status": "OK"}

    assert await api.set_season("AABBCCDD", Season.winter)

    assert mock_post.await_args_list[0].args == (session, "eco3/send/")
    assert mock_post.await_args_list[0].kwargs["json_payload"] == {
        "trama": "0AAABBCCDD00182F002000007F7F7F7F0F7F000000000000A10D"
    }
    assert mock_post.await_args_list[1].args == (session, "eco3/setdata/")
    assert mock_post.await_args_list[1].kwargs["json_payload"] == {
        "serial": "AABBCCDD",
        "data": '{"ws": 0}',
    }


@patch("pyintelliclima.api.REFRESH_DELAY", 0)
@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_free_cooling_updates_device_and_server_state(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort3API(session, token_headers={"TOKEN": "tok"})
    mock_post.return_value = {"status": "OK"}

    assert await api.set_free_cooling("AABBCCDD", FreeCoolingLevel.high)

    assert mock_post.await_args_list[0].args == (session, "eco3/send/")
    assert mock_post.await_args_list[0].kwargs["json_payload"] == {
        "trama": "0AAABBCCDD00182F002000007F7F7F7F737F000000000000030D"
    }
    assert mock_post.await_args_list[1].args == (session, "eco3/freecoolset/")
    assert mock_post.await_args_list[1].kwargs["json_payload"] == {
        "serial": "AABBCCDD",
        "value": 3,
    }
