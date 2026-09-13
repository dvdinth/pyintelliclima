"""Cross-checks the command builders against a port of the vendor app's frame code.

The port below is kept deliberately close to the JavaScript in the decompiled
IntelliClima+ app (`js/system/wifi.js`) so it can be re-verified against that source
rather than against our own helpers. It is an independent oracle, not shared logic:
`create_*_command` and `app_crea_trama` must agree byte for byte without either
calling into the other.

`ecoCreaTrama` and `eco3CreaTrama` are identical functions in the app - it even uses
the ECOCOMFORT 2.0 builder for an ECOCOMFORT 3 free-cooling write - so one port covers
both device families.
"""

from pyintelliclima.api import (
    create_advanced_settings_command,
    create_filter_reset_command,
    create_mode_speed_command,
    create_offsets_command,
    create_season_free_cooling_command,
)
from pyintelliclima.const import (
    FanMode,
    FanSpeed,
    FreeCoolingLevel,
    Season,
    SlaveRotation,
    ThresholdLevel,
)

SERIAL = "AABBCCDD"


def app_crc(buffer: str) -> str:
    """Port of `ecoCRC`."""
    crc = 0xFF
    polynom = 0x31
    for i in range(0, len(buffer), 2):
        crc = (crc ^ int(buffer[i : i + 2], 16)) & 0xFF
        for _ in range(8):
            crc = ((crc << 1) ^ polynom) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return f"{crc:02X}"


def app_crea_trama(serial: str, obj_id: str, dati: str, tipo: str) -> str:
    """Port of `ecoCreaTrama` / `eco3CreaTrama`."""
    length = 4 + 2 + 1 + (len(obj_id) + len(dati)) // 2 + 1
    buffer = serial + f"{length:04X}" + tipo + obj_id + dati
    return "0A" + buffer + app_crc(buffer) + "0D"


def test_mode_speed_command_matches_vendor_app():
    assert create_mode_speed_command(SERIAL, FanMode.sensor, FanSpeed.auto_set) == app_crea_trama(
        SERIAL, "00500000", "0410", "2F"
    )
    assert create_mode_speed_command(SERIAL, FanMode.alternate, FanSpeed.high) == app_crea_trama(
        SERIAL, "00500000", "0304", "2F"
    )
    assert create_mode_speed_command(SERIAL, FanMode.off, FanSpeed.off) == app_crea_trama(
        SERIAL, "00500000", "0000", "2F"
    )


def test_offsets_command_matches_vendor_app():
    # Offsets are scaled x100 and negatives are two's complement, so -5.0 degrees is
    # 0xFE0C and +1 % is 0x0064.
    assert create_offsets_command(SERIAL, -5.0, 1) == app_crea_trama(
        SERIAL, "00210000", "FE0C0064", "2F"
    )
    assert create_offsets_command(SERIAL, 0.1, -5) == app_crea_trama(
        SERIAL, "00210000", "000AFE0C", "2F"
    )


def test_advanced_settings_command_matches_vendor_app():
    assert create_advanced_settings_command(
        SERIAL,
        humidity_threshold=ThresholdLevel.low,
        voc_threshold=ThresholdLevel.medium,
        voc_threshold_advanced=True,
        lux_threshold=ThresholdLevel.high,
    ) == app_crea_trama(SERIAL, "00200000", "7F0103827F7F000000000000", "2F")

    # Untouched fields carry the app's 0x7F preserve marker.
    assert create_advanced_settings_command(
        SERIAL, slave_rotation=SlaveRotation.discordant
    ) == app_crea_trama(SERIAL, "00200000", "7F7F7F7F7F02000000000000", "2F")


def test_season_free_cooling_command_matches_vendor_app():
    # Season and free cooling share one byte, so each has its own nibble-sized
    # preserve marker: "7" for the season half, "F" for the free-cooling half.
    assert create_season_free_cooling_command(SERIAL, season=Season.summer) == app_crea_trama(
        SERIAL, "00200000", "7F7F7F7F1F7F000000000000", "2F"
    )
    assert create_season_free_cooling_command(
        SERIAL, free_cooling=FreeCoolingLevel.high
    ) == app_crea_trama(SERIAL, "00200000", "7F7F7F7F737F000000000000", "2F")


def test_filter_reset_command_matches_vendor_app():
    # `objID` is bare here rather than padded to four bytes, and the action byte is
    # 0x26 instead of the 0x2F used by every settings write.
    assert create_filter_reset_command(SERIAL) == app_crea_trama(
        SERIAL, "001A", "001A00000000", "26"
    )
