from enum import StrEnum

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


class SlaveRotation(StrEnum):
    """Direction of rotation for a slave/satellite unit relative to its master."""

    concordant = "1"
    discordant = "2"


class ThresholdLevel(StrEnum):
    """Sensor-mode threshold levels for humidity/VOC/luminosity triggers."""

    off = "0"
    low = "1"
    medium = "2"
    high = "3"
