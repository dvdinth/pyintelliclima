"""Several dataclasses for the IntelliClima api."""

import json
from dataclasses import asdict, dataclass, field
from typing import Literal

from pyintelliclima.const import (
    MODE_DIRECTION_MASK,
    SPEED_FLAG_ADVANCED,
    SPEED_FLAG_BOOST,
    SPEED_FLAG_NIGHT,
    SPEED_FLAG_PROFILED,
    SPEED_VALUE_MASK,
    FanMode,
    FanPreset,
    FanSpeed,
    FanSpeedState,
)

# ruff: noqa: N815

# Dataclass fields mirror the server's JSON keys verbatim - dacite matches by field name -
# including its camelCase and its master/slave wording. Our own API surface uses
# main/satellite instead.


@dataclass
class IntelliClimaLoginBody:
    """Login body for the login request."""

    manufacturer: str
    model: str
    platform: str
    serial: str
    uuid: str
    version: str | None
    language: str


@dataclass
class IntelliClimaLoginResponse:
    """Response format from the server to the login request."""

    id: str
    username: str
    password: str
    email: str
    name: str
    surname: str
    last_connection: str
    creation_date: str
    admin: str
    token: str
    reqid: str
    version: str
    status: str
    error: str
    user_devices: str
    query: str


@dataclass
class IntelliClimaHouseDevices:
    """Server response format for device in a house."""

    id: str
    isMaster: bool
    name: str
    tipo: str


@dataclass
class IntelliClimaGetHousesResponse:
    """Server response format for the get-house request."""

    status: Literal["OK", "NO_AUTH"]
    houses: dict[str, list[IntelliClimaHouseDevices]]
    hasHouses: bool
    hasMulti: bool
    cronoIDs: list[str]
    masterIDs: list[str]
    c900IDs: list[str]
    c900MasterIDs: list[str]
    ecoIDs: list[str]
    ecoMasterIDs: list[str]
    rhinoIDs: list[str]
    rhinoMasterIDs: list[str]
    eco3IDs: list[str]
    eco3MasterIDs: list[str]
    ecoplusIDs: list[str]
    ecoplusMasterIDs: list[str]


@dataclass
class IntelliClimaGetDeviceBody:
    """Request format for the device status polling request."""

    IDs: str
    ECOs: str
    C900s: str
    RHINOs: str
    ECO3s: str
    includi_eco: bool
    includi_ledot: bool
    includi_c900: bool
    includi_rhino: bool
    includi_eco3: bool


@dataclass
class IntelliClimaModelType:
    """Model type response format."""

    modello: str
    tipo: str


@dataclass
class IntelliClimaECODefaultProgram:
    """IntelliClima program definition as set in the IntelliClima+ app."""

    w: tuple[int, ...]
    s: tuple[int, ...]

    def to_formatted_str(self) -> str:
        """Format as dictionary string."""
        return json.dumps(asdict(self))


@dataclass
class IntelliClimaECOCustomProgram:
    """IntelliClima custom program definition as set in the IntelliClima+ app."""

    name: str
    graph: tuple[int, ...]

    def to_formatted_str(self) -> str:
        """Format as dictionary string."""
        return json.dumps(asdict(self))


@dataclass
class IntelliClimaVMCBase:
    """Status fields common to the ECOCOMFORT VMC family."""

    id: str
    crono_sn: str
    status: str
    online: str
    command: str
    model: IntelliClimaModelType
    name: str
    houses_id: str
    mode_set: FanMode
    mode_state: str
    speed_set: FanSpeed
    speed_state: str
    last_online: str
    creation_date: str
    fw: str
    mac: str
    macwifi: str
    conn_num: str
    conn_state: str
    role: str  # "1" = main unit, "2" = satellite unit
    rh_thrs: str
    lux_thrs: str
    voc_thrs: str | None
    slv_rot: str
    slv_addr: str
    offset_temp: str
    offset_hum: str
    year: str
    month: str
    day: str
    dow: str
    hour: str
    minute: str
    second: str
    dst: str
    mode_prev: str | None
    dir_state: str
    auto_cycle: str
    tamb: str
    rh: str
    voc_state: str
    plun: str | IntelliClimaECODefaultProgram
    pmar: str | IntelliClimaECODefaultProgram
    pmer: str | IntelliClimaECODefaultProgram
    pgio: str | IntelliClimaECODefaultProgram
    pven: str | IntelliClimaECODefaultProgram
    psab: str | IntelliClimaECODefaultProgram
    pdom: str | IntelliClimaECODefaultProgram
    pcustom: str | list[IntelliClimaECOCustomProgram] | None
    sfondo: str
    tperc: str | None
    fcool: str  # probably referring to 'free cooling' feature in summer-mode
    ws: str  # winter/summer mode ("0" = winter, "1" = summer)
    filter_from: str | None
    filter_active: str | None
    timezone: str | None
    co2: str | None
    sanification: str | None
    rssi: str | None
    aqi: str | None
    co2_thrs: str | None
    dev_state: str | None
    online_status: bool
    online_status_debug: str

    def __post_init__(self):
        """Convert the programs to string if necessary."""
        if isinstance(self.pcustom, list):
            self.pcustom = str([program.to_formatted_str() for program in self.pcustom]).replace(
                " ", ""
            )


@dataclass
class IntelliClimaECO2(IntelliClimaVMCBase):
    """Status data returned by an ECOCOMFORT 2.0 device."""


@dataclass
class IntelliClimaECO3(IntelliClimaVMCBase):
    """Status data returned by an ECOCOMFORT 3 device."""


@dataclass(frozen=True)
class FanState:
    """Decoded running state, as opposed to the `*_set` setpoints."""

    direction: FanMode
    speed: FanSpeedState
    preset: FanPreset
    profiled: bool
    advanced: bool
    boost: bool
    night: bool


def decode_fan_state(mode_state: str, speed_state: str) -> FanState:
    """Decode a device's reported `mode_state`/`speed_state` registers.

    Prefer this over the `mode_set`/`speed_set` fields: those hold the last value
    *commanded*, which is not what the unit is doing. The vendor app displays this
    pair and never those.

    `speed_state` packs the running speed in its low three bits and four flags in
    its high nibble; `mode_state` carries the airflow direction in its low nibble.
    The flag arithmetic mirrors the vendor app, including the order of the
    overrides: boost wins over the advanced bump, and night wins over both.

    Raises `ValueError` if either register is not an integer, or if the direction
    nibble is not a known `FanMode`.
    """
    mode_raw = int(mode_state)
    speed_raw = int(speed_state)

    night = bool(speed_raw & SPEED_FLAG_NIGHT)
    boost = bool(speed_raw & SPEED_FLAG_BOOST)
    advanced = bool(speed_raw & SPEED_FLAG_ADVANCED)
    profiled = bool(speed_raw & SPEED_FLAG_PROFILED)

    speed = speed_raw & SPEED_VALUE_MASK
    if advanced and 1 < speed < 5:
        speed += 1
    if boost:
        speed = 5
    if night:
        speed = 1

    direction = FanMode(str(mode_raw & MODE_DIRECTION_MASK))

    # Deliberately not a port of the app's own fan_mode: that returns -1 for 50 of
    # the 256 speed_state values, and conflates auto with program into one value
    # that its template then has to disambiguate by testing direction anyway.
    if direction is FanMode.sensor:
        preset = FanPreset.auto
    elif profiled:
        preset = FanPreset.program
    elif night or speed == FanSpeedState.sleep:
        preset = FanPreset.sleep
    elif direction is FanMode.off or speed == FanSpeedState.off:
        preset = FanPreset.off
    else:
        preset = FanPreset.manual

    return FanState(
        direction=direction,
        speed=FanSpeedState(speed),
        preset=preset,
        profiled=profiled,
        advanced=advanced,
        boost=boost,
        night=night,
    )


@dataclass
class IntelliClimaC800:
    """Not verified, converted from https://github.com/ruizmarc/homebridge-intelliclima."""

    id: str
    crono_sn: str
    multi_sn: str
    zone: str
    status: str
    online: str
    action: str
    model: IntelliClimaModelType
    name: str
    config: str
    appdata: str
    programs: str
    last_online: str
    creation_date: str
    agc_on: str
    cooler_on: str
    houses_id: str
    image: str
    c_mode: str
    t_amb: str
    t1w: str
    t2w: str
    t3w: str
    t1s: str
    t2s: str
    t3s: str
    jtw: str
    jts: str
    jh: str
    jm: str
    jdate: str
    tmans: str
    tmanw: str
    tafrost: str
    tset: str
    relay: str
    relayrh: str
    rh: str
    rhset: str
    rhrele: str
    rhabl: str
    ws: str
    day: str
    auxio: str
    alarms: str
    lastprogramwinter: str
    lastprogramsummer: str
    upd_client: str
    upd_server: str
    check_mode: str
    zones_id: str
    zones_crono_sn: str
    programs_acs: str
    power_detect: str
    manut_installatore: str
    manut_manutentore: str
    manut_pros_manutenzione: str
    manut_pros_verifica: str
    version: str
    protocol_type: str
    esp_at_version: str
    display_time_on: str
    brightness: str
    rgb_led: str
    degree: str
    adjust_temperature: str
    differential: str
    summertime: str
    timezone: str
    communication_frequency: str
    power_safe_enable: str
    optimization_function: str
    window_detection_enable: str
    home_page_visualization: str
    dhw_block: str
    password: str
    limit_setpoint_min: str
    limit_setpoint_max: str
    limit_ch_max: str
    limit_ch_min: str
    limit_dhw_max: str
    limit_dhw_min: str
    kd_slope: str
    kd_external_probe: str
    max_ch_heating_curve: str
    min_ch_heating_curve: str
    max_outside_heating_curve: str
    min_outside_heating_curve: str
    end_jolly_year: str
    end_jolly_month: str
    end_jolly_day: str
    end_jolly_week_day: str
    end_jolly_hours: str
    end_jolly_minutes: str
    end_jolly_seconds: str
    dhw_enable: str
    hvac_mode: str
    modulation_type: str
    ch_temperature_setting: str
    dhw_temperature_setting: str
    setpoints_dhw_winter_economy: str
    setpoints_dhw_winter_comfort: str
    window_detection_state: str
    battery_voltage: str
    battery_state: str
    wallplate_detect: str
    last_communication_year: str
    last_communication_month: str
    last_communication_day: str
    last_communication_week_day: str
    last_communication_hours: str
    last_communication_minutes: str
    last_communication_seconds: str
    last_comm: str
    next_comm: str
    wifi_last_comm_quality: str
    anomaly: str
    stato_upgrade_fw: str
    jolly_year_left: str
    jolly_month_left: str
    jolly_day_left: str
    jolly_week_left: str
    jolly_hours_left: str
    jolly_minutes_left: str
    jolly_seconds_left: str
    current_day: str
    current_month: str
    current_year: str
    t_high: str
    t_low: str
    usage: str
    usage_month_curr: str
    usage_month_prev: str
    usage_year: str
    anomalie_tacit_hours: str
    anomalie_tacit_actives: str
    kd_slope_2: str
    ch_setpoint_with_climatic_curve: str
    ch_temperature_out: str
    ch_temperature_in: str
    dhw_temperature_out: str
    fume_temperature: str
    outside_temperature: str
    thermal_sys_pressure: str
    power_percentage: str
    ot_field_validity: str
    current_setpoint_dhw: str
    heating_system: str
    wifi_ssid: str
    dhw_min: str
    dhw_max: str
    onoff_opentherm: str
    download_fw_percentage: str
    ch_min: str
    ch_max: str
    multizona: list[str]


@dataclass
class IntelliClimaFilterStatsEntry:
    """Per-speed-bucket runtime hours since `from_date`, used for filter wear calculation."""

    night_tot_hour: str
    low_tot_hour: str
    medium_tot_hour: str
    high_tot_hour: str
    boost_tot_hour: str


@dataclass
class IntelliClimaFilterStatus:
    """Server response format for the filter status calculation request."""

    serial: str
    is_active: bool
    from_date: str
    stats: list[IntelliClimaFilterStatsEntry]
    totale: float
    change_filter: bool


@dataclass
class IntelliClimaDevices:
    """Dataclass for storing intelliclima devices."""

    ecocomfort2_devices: dict[str, IntelliClimaECO2]
    c800_devices: dict[str, IntelliClimaC800]
    ecocomfort3_devices: dict[str, IntelliClimaECO3] = field(default_factory=dict)

    @property
    def num_devices(self):
        """List the total number of devices."""
        return (
            len(self.ecocomfort2_devices) + len(self.c800_devices) + len(self.ecocomfort3_devices)
        )

    @classmethod
    def empty(cls):
        """Initialize an empty instance of this class with no devices."""
        return cls({}, {})


AllIntelliClimaDevices = IntelliClimaECO2 | IntelliClimaECO3 | IntelliClimaC800
