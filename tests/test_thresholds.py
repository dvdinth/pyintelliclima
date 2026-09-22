"""Cross-checks the threshold decoder against the vendor app's own decode.

The port below mirrors `impostazioni-ecocomfort2.js:178-194`, which the app repeats
verbatim for every generation in `elenco-case.js`. It is an independent oracle:
`decode_threshold` must agree with it without either calling the other.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import IntelliClimaAPI, create_advanced_settings_command
from pyintelliclima.const import ThresholdLevel
from pyintelliclima.intelliclima_types import (
    IntelliClimaECO3,
    ThresholdSetting,
    decode_threshold,
)


def app_decode(raw: str) -> tuple[int, bool]:
    """Port of the app's threshold decode."""
    value = int(raw)
    advanced = False
    if value >= 128:
        advanced = value > 128
        value -= 128
    return value, advanced


@pytest.mark.parametrize("raw", ["0", "1", "2", "3", "128", "129", "130", "131"])
def test_decode_threshold_matches_vendor_app(raw: str):
    level, advanced = app_decode(raw)
    assert decode_threshold(raw) == ThresholdSetting(ThresholdLevel(str(level)), advanced)


def test_decode_threshold_rejects_an_undefined_level():
    with pytest.raises(ValueError, match="4"):
        decode_threshold("4")



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


@pytest.mark.asyncio
async def test_device_threshold_properties():
    device = await _eco3(rh_thrs="130", co2_thrs="1", lux_thrs="3")

    assert device.humidity_threshold == ThresholdSetting(ThresholdLevel.medium, advanced=True)
    assert device.co2_threshold == ThresholdSetting(ThresholdLevel.low, advanced=False)
    assert device.luminosity_threshold is ThresholdLevel.high


@pytest.mark.asyncio
async def test_luminosity_threshold_rejects_a_flag_bit():
    # Neither generation has an advanced option for luminosity, so a flag bit here would
    # mean that understanding is wrong. Masking it away would hide that.
    device = await _eco3(lux_thrs="129")

    with pytest.raises(ValueError, match="129"):
        _ = device.luminosity_threshold



@pytest.mark.asyncio
async def test_device_threshold_property_is_none_when_unreported():
    device = await _eco3(rh_thrs="")

    assert device.humidity_threshold is None


@pytest.mark.parametrize("level", list(ThresholdLevel))
@pytest.mark.parametrize("advanced", [False, True])
def test_threshold_write_decodes_back_to_what_was_written(level: ThresholdLevel, advanced: bool):
    """The byte the command builder emits must read back as the same setting.

    This is the whole point of decoding: a partial write has to resend the other fields,
    and it can only do that if what the device reports round-trips.
    """
    command = create_advanced_settings_command(
        "AABBCCDD", humidity_threshold=level, humidity_threshold_advanced=advanced
    )
    # Frame prefix is 0A + serial + length + action + objID = 24 hex chars, then the
    # data bytes; the humidity threshold is the second of those, right after `role`.
    rh_byte = int(command[26:28], 16)

    expected_advanced = advanced and level is not ThresholdLevel.off
    assert decode_threshold(str(rh_byte)) == ThresholdSetting(level, expected_advanced)
