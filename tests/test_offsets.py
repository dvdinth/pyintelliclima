"""Tests for the calibration offset decode and its round trip through a write.

The registers are the one pair the vendor app reads and writes in different units: it
displays `offset_temp / 100` (`impostazioni-ecocomfort2.js:149-155`) but hands the raw
register straight back to its own write.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import IntelliClimaAPI, create_offsets_command
from pyintelliclima.intelliclima_types import IntelliClimaECO3, decode_offset

SERIAL = "AABBCCDD"


async def _eco3(**overrides: str) -> IntelliClimaECO3:
    """Poll one device off the ECOCOMFORT 3 fixture, with the given fields replaced."""
    fixture = Path(__file__).parent / "fixtures" / "ecocomfort3_status.json"
    response = json.loads(fixture.read_text())
    response["data"][0].update(overrides)

    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.ecocomfort3_ids = ["30"]
    with patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = response
        devices = await api.get_all_device_status()
    return devices.ecocomfort3_devices["30"]


def test_decode_offset_scales_signed_hundredths():
    # Values observed on the wire: the server reports the sign itself, so there is no
    # two's complement to undo here the way there is in the command frame.
    assert decode_offset("150") == 1.5
    assert decode_offset("-230") == -2.3
    assert decode_offset("0") == 0


@pytest.mark.asyncio
async def test_device_offset_properties():
    device = await _eco3(offset_temp="-230", offset_hum="300")

    assert device.temperature_offset == -2.3
    assert device.humidity_offset == 3


@pytest.mark.asyncio
async def test_device_offset_properties_are_none_when_unreported():
    device = await _eco3(offset_temp="", offset_hum="")

    assert device.temperature_offset is None
    assert device.humidity_offset is None


@pytest.mark.asyncio
async def test_decoded_offset_survives_a_partial_write():
    """Resending an unchanged offset must not scale it a second time.

    This is what the raw `offset_temp` field gets wrong: both offsets share one
    register, so a caller changing only the humidity has to resend the temperature.
    """
    device = await _eco3(offset_temp="-230", offset_hum="0")
    assert device.temperature_offset is not None

    resent = create_offsets_command(SERIAL, device.temperature_offset, 5)
    unchanged = create_offsets_command(SERIAL, -2.3, 5)

    assert resent == unchanged
    # -2.3 degrees is -230 = 0xFF1A, and 5 % is 500 = 0x01F4.
    assert "FF1A01F4" in resent
