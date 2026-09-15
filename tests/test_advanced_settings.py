from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import (
    IntelliClimaEcocomfort2API,
    create_advanced_settings_command,
    create_offsets_command,
)
from pyintelliclima.const import FreeCoolingLevel, Season, SatelliteRotation, ThresholdLevel

# --- create_offsets_command: golden values from real mitmproxy captures (2026-07-29) ---
#
# The captured device serial is replaced by a placeholder throughout, so the payload
# bytes are as captured but each CRC is re-derived. tests/test_vendor_frames.py checks
# the same builders against an independent port of the vendor app's own frame code.


@pytest.mark.parametrize(
    ("temperature_offset", "humidity_offset", "expected"),
    [
        (1.5, 0, "0A1234567800102F0021000000960000AE0D"),
        (-2.3, 0, "0A1234567800102F00210000FF1A0000D70D"),
        (0, 3, "0A1234567800102F002100000000012C750D"),
        (0, -5, "0A1234567800102F002100000000FE0C720D"),
        (0, 0, "0A1234567800102F00210000000000007A0D"),
    ],
    ids=["temp_1.5", "temp_-2.3", "hum_3", "hum_-5", "zero"],
)
def test_create_offsets_command_matches_capture(temperature_offset, humidity_offset, expected):
    assert create_offsets_command("12345678", temperature_offset, humidity_offset) == expected


# --- create_advanced_settings_command: golden values from real mitmproxy captures ---


def test_create_advanced_settings_command_rotation_concordant():
    command = create_advanced_settings_command("12345678", satellite_rotation=SatelliteRotation.concordant)
    assert command == "0A1234567800182F002000007F7F7F7F7F010000000000002F0D"


def test_create_advanced_settings_command_rotation_discordant():
    command = create_advanced_settings_command("12345678", satellite_rotation=SatelliteRotation.discordant)
    assert command == "0A1234567800182F002000007F7F7F7F7F02000000000000250D"


def test_create_advanced_settings_command_thresholds_combined():
    """All three thresholds share one register - all must be sent together."""
    command = create_advanced_settings_command(
        "12345678",
        humidity_threshold=ThresholdLevel.high,
        humidity_threshold_advanced=True,
        lux_threshold=ThresholdLevel.low,
        voc_threshold=ThresholdLevel.low,
        voc_threshold_advanced=True,
    )
    assert command == "0A1234567800182F002000007F8301817F7F000000000000C30D"


def test_create_advanced_settings_command_defaults_all_preserved():
    """With no fields set, every settable byte is 0x7F (preserve)."""
    command = create_advanced_settings_command("12345678")
    assert "7F7F7F7F7F" in command


def test_create_advanced_settings_command_threshold_off_ignores_advanced_flag():
    command = create_advanced_settings_command(
        "12345678", humidity_threshold=ThresholdLevel.off, humidity_threshold_advanced=True
    )
    # byte after the leading "7F" preserve byte is the humidity threshold byte
    payload = command[16 : 16 + 2]
    assert payload == "00"


# --- async wrapper methods ---


@pytest.mark.asyncio
@patch("pyintelliclima.api.REFRESH_DELAY", 0)
@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_season(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort2API(session, token_headers={"TOKEN": "tok"})
    mock_post.return_value = {"status": "OK", "serial": "12345678"}

    result = await api.set_season("12345678", Season.winter)

    assert result is True
    # Without the command frame the device keeps its old season: setdata/ only moves
    # the cloud-side record, which is what made this look like it worked.
    assert mock_post.await_args_list[0].args == (session, "eco/send/")
    assert mock_post.await_args_list[0].kwargs["json_payload"] == {
        "trama": "0A1234567800182F002000007F7F7F7F0F7F000000000000870D"
    }
    assert mock_post.await_args_list[1].args == (session, "eco/setdata/")
    assert mock_post.await_args_list[1].kwargs["json_payload"] == {
        "serial": "12345678",
        "data": '{"ws": 0}',
    }


@pytest.mark.asyncio
@patch("pyintelliclima.api.REFRESH_DELAY", 0)
@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_free_cooling(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort2API(session, token_headers={"TOKEN": "tok"})
    mock_post.return_value = {"status": "OK", "value": 2, "serial": "12345678"}

    result = await api.set_free_cooling("12345678", FreeCoolingLevel.medium)

    assert result is True
    assert mock_post.await_args_list[0].args == (session, "eco/send/")
    assert mock_post.await_args_list[0].kwargs["json_payload"] == {
        "trama": "0A1234567800182F002000007F7F7F7F727F0000000000006C0D"
    }
    assert mock_post.await_args_list[1].args == (session, "eco/freecoolset/")
    assert mock_post.await_args_list[1].kwargs["json_payload"] == {
        "serial": "12345678",
        "value": 2,
    }


@pytest.mark.asyncio
@patch("pyintelliclima.api.REFRESH_DELAY", 0)
@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_temperature_and_humidity_offsets(mock_post):
    session = MagicMock()
    api = IntelliClimaEcocomfort2API(session, token_headers={"TOKEN": "tok"})
    mock_post.return_value = {"status": "OK"}

    result = await api.set_temperature_and_humidity_offsets("12345678", 1.5, 0)

    assert result is True
    called_args, called_kwargs = mock_post.call_args
    assert called_args[1] == "eco/send/"
    assert called_kwargs["json_payload"] == {"trama": "0A1234567800102F0021000000960000AE0D"}


@pytest.mark.asyncio
@patch.object(IntelliClimaEcocomfort2API, "set_advanced_settings", new_callable=AsyncMock)
async def test_set_slave_rotation_calls_set_advanced_settings(mock_set_advanced):
    session = MagicMock()
    api = IntelliClimaEcocomfort2API(session, token_headers={})
    mock_set_advanced.return_value = True

    result = await api.set_satellite_rotation("12345678", SatelliteRotation.concordant)

    assert result is True
    mock_set_advanced.assert_awaited_once_with("12345678", satellite_rotation=SatelliteRotation.concordant)
