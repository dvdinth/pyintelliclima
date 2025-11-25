from pyintelliclima.api import (
    bytes_to_hex,
    checksum_crc8_nrsc5,
    create_mode_speed_command,
    hex_to_bytes,
)


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


def test_create_mode_speed_command_structure():
    device_sn = "12345678"
    mode = "04"
    speed = "10"

    command = create_mode_speed_command(device_sn, mode, speed)

    assert isinstance(command, str)
    assert command.startswith("0A" + device_sn)
    assert command.endswith("0D")

    data = bytearray(hex_to_bytes(command))
    assert data[0] == 0x0A
    assert data[-1] == 0x0D

    computed_crc = checksum_crc8_nrsc5(data[1:-2])
    assert data[-2] == computed_crc
