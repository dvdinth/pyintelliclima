"""Tests for decode_fan_state, including a brute-force check against the vendor app.

`app_speed_and_flags` is a port of the `speed_state` decode in
`js/system/sync.js:947-975`, kept close to the JavaScript so it can be re-checked
against the decompiled app. It is used as an oracle across every possible register
value, since this is the part of the decode that is easy to get subtly wrong.
"""

import json
from pathlib import Path

import pytest

from pyintelliclima.const import FanMode, FanPreset, FanSpeedState
from pyintelliclima.intelliclima_types import decode_fan_state


def app_speed_and_flags(speed_state: int) -> tuple[int, bool, bool, bool, bool]:
    """Port of the app's speed decode. Returns (speed, profiled, advanced, boost, night)."""
    bin_ = format(speed_state & 0xFF, "08b")
    profiled = bin_[3] == "1"
    night = bin_[0] == "1"
    boost = bin_[1] == "1"
    advanced = bin_[2] == "1"

    speed = speed_state & 0x7
    if advanced and 1 < speed < 5:
        speed += 1
    if boost:
        speed = 5
    if night:
        speed = 1

    return speed, profiled, advanced, boost, night


def test_decode_matches_vendor_app_for_every_speed_state():
    for raw in range(256):
        speed, profiled, advanced, boost, night = app_speed_and_flags(raw)

        if speed > FanSpeedState.boost:
            # Low bits 6 and 7 are not speeds the device defines. The app renders
            # them as a blank speed name; we reject them rather than invent one.
            with pytest.raises(ValueError, match="not a valid FanSpeedState"):
                decode_fan_state("1", str(raw))
            continue

        state = decode_fan_state("1", str(raw))
        assert (state.speed, state.profiled, state.advanced, state.boost, state.night) == (
            speed,
            profiled,
            advanced,
            boost,
            night,
        )


def test_direction_is_the_mode_state_low_nibble():
    # The app masks mode_state with 0x1f and then reads direction as & 0xF, so the
    # upper bits are flags that must not leak into the direction.
    for raw in range(256):
        if (raw & 0x0F) > 4:
            continue
        assert decode_fan_state(str(raw), "0").direction is FanMode(str(raw & 0x0F))


def test_decode_fixture_snapshot():
    fixture = json.loads((Path(__file__).parent / "fixtures" / "ecocomfort3_status.json").read_text())
    device = fixture["data"][0]

    state = decode_fan_state(device["mode_state"], device["speed_state"])

    # mode_state 20 = 0x14 -> sensor; speed_state 19 = 0x13 -> profiled + Vel2
    assert state.direction is FanMode.sensor
    assert state.speed is FanSpeedState.speed2
    assert state.preset is FanPreset.auto
    assert state.profiled is True
    assert state.boost is False


def test_boost_overrides_the_running_speed():
    state = decode_fan_state("1", str(0x40 | 0x02))

    assert state.boost is True
    assert state.speed is FanSpeedState.boost
    assert state.preset is FanPreset.manual


def test_night_wins_over_boost():
    state = decode_fan_state("1", str(0x80 | 0x40 | 0x04))

    assert state.speed is FanSpeedState.sleep
    assert state.preset is FanPreset.sleep


def test_advanced_control_bumps_the_speed_one_step():
    assert decode_fan_state("1", str(0x20 | 0x03)).speed is FanSpeedState.speed3
    # Sleep and the top speed are both left alone by the bump.
    assert decode_fan_state("1", str(0x20 | 0x01)).speed is FanSpeedState.sleep
    assert decode_fan_state("1", str(0x20 | 0x05)).speed is FanSpeedState.boost


def test_preset_prefers_auto_over_program():
    # The app conflates these two and disambiguates in its template; direction 4
    # means the sensors are driving even when the profiled bit is also set.
    assert decode_fan_state("4", str(0x10 | 0x03)).preset is FanPreset.auto
    assert decode_fan_state("1", str(0x10 | 0x03)).preset is FanPreset.program


def test_preset_off():
    assert decode_fan_state("0", "0").preset is FanPreset.off
    assert decode_fan_state("1", "0").preset is FanPreset.off


def test_unknown_direction_nibble_raises():
    with pytest.raises(ValueError, match="not a valid FanMode"):
        decode_fan_state("7", "0")
