from enum import IntEnum, StrEnum

# API endpoints
API_BASE_URL = "https://intelliclima.fantinicosmi.it"
API_MONO = "/server_v1_mono/api/"

REFRESH_DELAY = 5  # seconds


class FanSpeed(StrEnum):
    """Speed setpoints, as written to the device's `oper_ts` register.

    Values are the register byte in decimal, which is also how `sync/cronos400`
    reports the last commanded speed back in `speed_set`.
    """

    off = "0"
    sleep = "1"
    low = "2"
    medium = "3"
    high = "4"
    auto = "16"  # 0x10 - speed is left to the sensors or the weekly program


class FanMode(StrEnum):
    """Fan mode/direction options for EcoComfort VMC devices."""

    off = "0"
    inward = "1"
    outward = "2"
    alternate = "3"
    sensor = "4"


# `speed_state` bit flags. The running speed itself sits in the low three bits.
SPEED_FLAG_PROFILED = 0x10  # speed comes from the weekly program or the sensors
SPEED_FLAG_ADVANCED = 0x20  # an advanced threshold is engaged: run one step faster
SPEED_FLAG_BOOST = 0x40
SPEED_FLAG_NIGHT = 0x80
SPEED_VALUE_MASK = 0x07

# `mode_state` carries the airflow direction in its low nibble.
MODE_DIRECTION_MASK = 0x0F


class FanSpeedState(IntEnum):
    """Actual running speed, decoded from the `speed_state` bitfield.

    Distinct from `FanSpeed`, which holds setpoints in the device's own encoding:
    a device set to `FanSpeed.auto` still reports a concrete speed here.
    """

    off = 0
    sleep = 1
    speed1 = 2
    speed2 = 3
    speed3 = 4
    boost = 5


class FanPreset(StrEnum):
    """What is currently driving the fan."""

    off = "off"
    sleep = "sleep"
    manual = "manual"
    program = "program"
    auto = "auto"


class Season(StrEnum):
    """Winter/summer mode for EcoComfort VMC devices."""

    winter = "0"
    summer = "1"


class FreeCoolingLevel(StrEnum):
    """Free cooling intake/outdoor delta threshold, only effective in summer mode."""

    off = "0"
    low = "1"
    medium = "2"
    high = "3"


class SatelliteRotation(StrEnum):
    """Direction of rotation for a satellite unit relative to its main unit."""

    concordant = "1"
    discordant = "2"


class ThresholdLevel(StrEnum):
    """Sensor-mode threshold levels for humidity/VOC/luminosity triggers."""

    off = "0"
    low = "1"
    medium = "2"
    high = "3"
