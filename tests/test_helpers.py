from __future__ import annotations

import binascii
import datetime
from unittest.mock import patch

import pytest

from pyintelliclima.api import (
    bytes_to_hex,
    checksum_crc8_nrsc5,
    create_mode_speed_command,
    create_request_token,
    hex_to_bytes,
)
from pyintelliclima.const import FanMode, FanSpeed


def test_hex_bytes_roundtrip():
    original = "0A1234FF"
    as_bytes = hex_to_bytes(original)
    back = bytes_to_hex(bytearray(as_bytes))
    assert back.upper() == original


def test_checksum_crc8_nrsc5_known_vector():
    data = bytearray(b"\x01\x02\x03\x04")
    crc = checksum_crc8_nrsc5(data)
    assert isinstance(crc, int)
    assert 0 <= crc <= 0xFF


def test_checksum_crc8_nrsc5_deterministic():
    data = bytearray(b"\xab\xcd\xef")
    assert checksum_crc8_nrsc5(data) == checksum_crc8_nrsc5(data)


# --- create_mode_speed_command ---

# Standard 8-char SN used throughout; device SNs are always 8 hex chars (4 bytes).
SN = "AABBCCDD"


def _decode(cmd: str) -> bytearray:
    return bytearray(binascii.unhexlify(cmd))


def test_create_mode_speed_command_even_sn():
    """Baseline: even-length SN produces a valid, uppercase hex command."""
    cmd = create_mode_speed_command(SN, FanMode.off, FanSpeed.off)
    assert cmd == cmd.upper()
    assert len(cmd) % 2 == 0


def test_create_mode_speed_command_rejects_non_standard_sn():
    """A serial that is not four bytes cannot be encoded into the frame.

    The length field is hardcoded for an eight-character serial, so padding a short one
    would produce a frame the device misreads. Failing here is the safe outcome.
    """
    with pytest.raises(binascii.Error):
        create_mode_speed_command("1234567", FanMode.inward, FanSpeed.low)


def test_create_mode_speed_command_embeds_the_sn_verbatim():
    """The serial reaches the frame unchanged, as the vendor app sends it."""
    received: list[str] = []

    with patch(
        "pyintelliclima.api.hex_to_bytes",
        side_effect=lambda x: (received.append(x), hex_to_bytes(x))[1],
    ):
        create_mode_speed_command(SN, FanMode.inward, FanSpeed.low)

    assert received[0].startswith("0A" + SN)


def test_create_mode_speed_command_frame_structure():
    """Frame: starts with 0x0A, ends with 0x0D, CRC at second-to-last byte."""
    cmd = create_mode_speed_command(SN, FanMode.sensor, FanSpeed.medium)
    data = _decode(cmd)

    assert data[0] == 0x0A
    assert data[-1] == 0x0D
    # CRC covers bytes[1:-2]
    assert data[-2] == checksum_crc8_nrsc5(data[1:-2])


def test_create_mode_speed_command_length():
    """For the standard 8-char (4-byte) SN the total frame is 16 bytes (32 hex chars):
    0A + 4B SN + 7B fixed + 1B mode + 1B speed + 1B CRC + 0D."""
    cmd = create_mode_speed_command(SN, FanMode.off, FanSpeed.off)
    assert len(cmd) == 32


def test_create_mode_speed_command_mode_speed_bytes():
    """Mode and speed are placed at the correct byte offsets for a 4-byte SN."""
    # byte layout: [0]=0A, [1:5]=SN, [5:12]=fixed, [12]=mode, [13]=speed, [14]=CRC, [15]=0D
    cmd = create_mode_speed_command(SN, FanMode.alternate, FanSpeed.high)
    data = _decode(cmd)
    assert data[12] == int(FanMode.alternate)  # 3
    assert data[13] == int(FanSpeed.high)  # 4


def test_create_mode_speed_command_auto_speed_encoding():
    """FanSpeed.auto='16' encodes to byte 0x10.

    Enum values are the protocol byte in decimal, matching what the device reports
    back in `speed_set`, and the command builder formats them as hex.
    """
    cmd = create_mode_speed_command(SN, FanMode.sensor, FanSpeed.auto)
    data = _decode(cmd)
    assert data[13] == 0x10


def test_create_mode_speed_command_crc_changes_with_content():
    """CRC reflects the full payload: different mode/speed produce different checksums."""
    cmd_a = create_mode_speed_command(SN, FanMode.inward, FanSpeed.low)
    cmd_b = create_mode_speed_command(SN, FanMode.outward, FanSpeed.high)
    data_a = _decode(cmd_a)
    data_b = _decode(cmd_b)
    assert data_a[-2] != data_b[-2]


@pytest.mark.parametrize(
    "sn",
    [
        "AABBCCDD",  # the standard case
        "12345678",  # all numbers
    ],
)
def test_create_mode_speed_command_standard_sn_lengths(sn: str):
    """A standard eight-character serial produces a 32-char command."""
    cmd = create_mode_speed_command(sn, FanMode.inward, FanSpeed.medium)
    assert len(cmd) == 32
    data = _decode(cmd)
    assert data[0] == 0x0A
    assert data[-1] == 0x0D
    assert data[-2] == checksum_crc8_nrsc5(data[1:-2])


def test_create_request_token_format():
    # The app hashes the date as DDMMYYYY in local time, zero-padded, four-digit year.
    with patch("pyintelliclima.api.date") as mock_date:
        mock_date.today.return_value = datetime.date(1999, 2, 5)
        assert (
            create_request_token()
            == "37561eec3f0a246abcddb29acc2126823eb61ed05122e23c513f3baa3b64ecfd"
        )
