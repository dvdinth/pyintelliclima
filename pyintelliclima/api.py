"""API client for IntelliClima integration."""

import asyncio
import binascii
import hashlib
import json
import logging
import uuid
from dataclasses import asdict
from typing import Any, ClassVar, Literal

from aiohttp import ClientError, ClientSession
from dacite import from_dict

from .const import (
    API_BASE_URL,
    API_MONO,
    REFRESH_DELAY,
    FanMode,
    FanSpeed,
    FreeCoolingLevel,
    Season,
    SlaveRotation,
    ThresholdLevel,
)
from .intelliclima_types import (
    IntelliClimaDevices,
    IntelliClimaECO,
    IntelliClimaECO3,
    IntelliClimaFilterStatus,
    IntelliClimaLoginBody,
)

LOGGER = logging.getLogger(__name__)


def generate_read_url(path: str) -> str:
    """Helper function for generating the request url."""
    return f"{API_BASE_URL}{API_MONO}{path}"


async def post_to_session(
    session: ClientSession,
    api_url: str,
    headers: dict[str, Any] | None = None,
    json_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a POST HTTP request and convert response back to dictionary."""
    async with session.post(generate_read_url(api_url), headers=headers, json=json_payload) as resp:
        resp.raise_for_status()
        response_text = await resp.text()
        response = json.loads(response_text)
        if response.get("status") != "OK":
            msg = f"Got non-OK response status: {response.get('status')}"
            raise IntelliClimaAPIError(msg)
    return response


def hex_to_bytes(x: str) -> bytes:
    """Converts hex string to bytes."""
    return binascii.unhexlify(x)


def bytes_to_hex(x: bytearray) -> str:
    """Converts bytearray to hex string."""
    return binascii.hexlify(x).decode()


def checksum_crc8_nrsc5(
    data_bytes: bytearray, poly: Literal[49] = 0x31, init: Literal[255] = 0xFF
) -> int:
    """Calculates 8 bit CRC8 NRSC5 checksum."""
    crc = init
    for b in data_bytes:
        crc ^= b
        for _ in range(8):
            if (crc & 0x80) != 0:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def create_mode_speed_command(device_sn: str, mode: FanMode, speed: FanSpeed) -> str:
    """Creates the api request command that sets mode and speed for a certain device."""
    LOGGER.debug(
        "Setting mode & speed for device %s to mode: %s, speed %s",
        device_sn,
        mode,
        speed,
    )
    # unhexlify requires an even-length string (2 hex chars per byte)
    padded_sn = "0" + device_sn if len(device_sn) % 2 else device_sn
    partial_command = "0A" + padded_sn + "000E2F00500000" + f"{int(mode):02d}" + f"{int(speed):02d}"
    base_data = bytearray(hex_to_bytes(partial_command))
    base_data.append(0x00)  # Placeholder for checksum
    base_data.append(0x0D)  # Termination byte

    cs = checksum_crc8_nrsc5(base_data[1:-2])
    base_data[-2] = cs  # Set checksum byte

    return bytes_to_hex(base_data).upper()


def create_offsets_command(device_sn: str, temperature_offset: float, humidity_offset: int) -> str:
    """Creates the api request command that sets temperature and humidity calibration offsets.

    Both offsets share the same device register, so both must be sent together - pass the
    device's current value for whichever offset isn't being changed.
    """
    padded_sn = "0" + device_sn if len(device_sn) % 2 else device_sn
    temp_raw = round(temperature_offset * 100) & 0xFFFF
    hum_raw = round(humidity_offset * 100) & 0xFFFF
    partial_command = "0A" + padded_sn + "00102F00210000" + f"{temp_raw:04X}" + f"{hum_raw:04X}"
    base_data = bytearray(hex_to_bytes(partial_command))
    base_data.append(0x00)  # Placeholder for checksum
    base_data.append(0x0D)  # Termination byte

    cs = checksum_crc8_nrsc5(base_data[1:-2])
    base_data[-2] = cs  # Set checksum byte

    return bytes_to_hex(base_data).upper()


def create_advanced_settings_command(
    device_sn: str,
    *,
    humidity_threshold: ThresholdLevel | None = None,
    humidity_threshold_advanced: bool = False,
    voc_threshold: ThresholdLevel | None = None,
    voc_threshold_advanced: bool = False,
    lux_threshold: ThresholdLevel | None = None,
    slave_rotation: SlaveRotation | None = None,
) -> str:
    """Creates the api request command for the shared humidity/VOC/lux threshold and
    slave-rotation register.

    A field left as `None` is preserved unchanged on the device (sent as `0x7F`), matching
    the same "preserve" convention documented for this device's BLE protocol in the
    esphome-ecocomfort2 project. Only pass the field(s) you actually want to change.
    """

    def threshold_byte(level: ThresholdLevel | None, advanced: bool) -> int:
        if level is None:
            return 0x7F
        value = int(level)
        return value + 0x80 if advanced and value else value

    padded_sn = "0" + device_sn if len(device_sn) % 2 else device_sn
    rh_byte = threshold_byte(humidity_threshold, humidity_threshold_advanced)
    lux_byte = threshold_byte(lux_threshold, advanced=False)
    voc_byte = threshold_byte(voc_threshold, voc_threshold_advanced)
    rotation_byte = 0x7F if slave_rotation is None else int(slave_rotation)

    partial_command = (
        "0A"
        + padded_sn
        + "00182F00200000"
        + "7F"
        + f"{rh_byte:02X}"
        + f"{lux_byte:02X}"
        + f"{voc_byte:02X}"
        + "7F"
        + f"{rotation_byte:02X}"
        + "000000000000"
    )
    base_data = bytearray(hex_to_bytes(partial_command))
    base_data.append(0x00)  # Placeholder for checksum
    base_data.append(0x0D)  # Termination byte

    cs = checksum_crc8_nrsc5(base_data[1:-2])
    base_data[-2] = cs  # Set checksum byte

    return bytes_to_hex(base_data).upper()


def create_season_free_cooling_command(
    device_sn: str,
    *,
    season: Season | None = None,
    free_cooling: FreeCoolingLevel | None = None,
) -> str:
    """Create an ECOCOMFORT 3 command for the shared season/free-cooling byte.

    The two values occupy one nibble each. A value left as ``None`` is encoded
    with the vendor app's preserve marker for that nibble.
    """
    padded_sn = "0" + device_sn if len(device_sn) % 2 else device_sn
    season_nibble = "7" if season is None else f"{int(season):X}"
    free_cooling_nibble = "F" if free_cooling is None else f"{int(free_cooling):X}"
    partial_command = (
        "0A"
        + padded_sn
        + "00182F00200000"
        + "7F7F7F7F"
        + season_nibble
        + free_cooling_nibble
        + "7F000000000000"
    )
    base_data = bytearray(hex_to_bytes(partial_command))
    base_data.append(0x00)
    base_data.append(0x0D)

    base_data[-2] = checksum_crc8_nrsc5(base_data[1:-2])
    return bytes_to_hex(base_data).upper()


class IntelliClimaAPIError(Exception):
    """Exception for API errors."""


class IntelliClimaAuthError(IntelliClimaAPIError):
    """Exception for authentication errors."""


class _IntelliClimaVMCAPI:
    """Shared API client for the ECOCOMFORT VMC family."""

    _endpoint_prefix: ClassVar[str]

    def __init__(self, session: ClientSession, token_headers: dict[str, Any]) -> None:
        """Initialize the ECOCOMFORT API client."""
        self._session = session
        self._token_headers = token_headers

    async def set_token_headers(self, token_headers: dict[str, Any]) -> None:
        """Set the ECOCOMFORT API token headers."""
        self._token_headers = token_headers

    async def _send_command(self, command: str) -> bool:
        """Send a command frame to an ECOCOMFORT device."""
        LOGGER.debug("Sending command: %s", command)
        await post_to_session(
            self._session,
            f"{self._endpoint_prefix}/send/",
            headers=self._token_headers,
            json_payload={"trama": command},
        )
        await asyncio.sleep(REFRESH_DELAY)
        return True

    async def turn_off(self, device_sn: str) -> bool:
        """Turn off an ECOCOMFORT device."""
        return await self.set_mode_speed(device_sn, mode=FanMode.off, speed=FanSpeed.off)

    async def set_mode_speed(self, device_sn: str, mode: FanMode, speed: FanSpeed) -> bool:
        """Set the mode and speed of an ECOCOMFORT device."""
        command = create_mode_speed_command(device_sn, mode, speed)
        return await self._send_command(command)

    async def set_mode_speed_auto(self, device_sn: str) -> bool:
        """Set the auto preset mode and speed."""
        return await self.set_mode_speed(device_sn, mode=FanMode.sensor, speed=FanSpeed.auto_set)

    async def set_temperature_and_humidity_offsets(
        self, device_sn: str, temperature_offset: float, humidity_offset: int
    ) -> bool:
        """Set temperature and humidity calibration offsets."""
        command = create_offsets_command(device_sn, temperature_offset, humidity_offset)
        return await self._send_command(command)

    async def _set_advanced_settings(
        self,
        device_sn: str,
        *,
        humidity_threshold: ThresholdLevel | None = None,
        humidity_threshold_advanced: bool = False,
        voc_threshold: ThresholdLevel | None = None,
        voc_threshold_advanced: bool = False,
        lux_threshold: ThresholdLevel | None = None,
        slave_rotation: SlaveRotation | None = None,
    ) -> bool:
        """Set shared ECOCOMFORT sensor thresholds and/or slave rotation."""
        command = create_advanced_settings_command(
            device_sn,
            humidity_threshold=humidity_threshold,
            humidity_threshold_advanced=humidity_threshold_advanced,
            voc_threshold=voc_threshold,
            voc_threshold_advanced=voc_threshold_advanced,
            lux_threshold=lux_threshold,
            slave_rotation=slave_rotation,
        )
        return await self._send_command(command)


class IntelliClimaEcocomfortAPI(_IntelliClimaVMCAPI):
    """API client for specific ECOCOMFORT 2.0 communication."""

    _endpoint_prefix = "eco"

    async def set_season(self, device_sn: str, season: Season) -> bool:
        """Set winter/summer mode for an ecocomfort device."""
        payload = {"serial": device_sn, "data": json.dumps({"ws": int(season)})}
        await post_to_session(
            self._session,
            "eco/setdata/",
            headers=self._token_headers,
            json_payload=payload,
        )
        await asyncio.sleep(REFRESH_DELAY)
        return True

    async def set_free_cooling(self, device_sn: str, level: FreeCoolingLevel) -> bool:
        """Set the free cooling level for an ecocomfort device (only effective in summer mode)."""
        payload = {"serial": device_sn, "value": int(level)}
        await post_to_session(
            self._session,
            "eco/freecoolset/",
            headers=self._token_headers,
            json_payload=payload,
        )
        await asyncio.sleep(REFRESH_DELAY)
        return True

    async def set_advanced_settings(
        self,
        device_sn: str,
        *,
        humidity_threshold: ThresholdLevel | None = None,
        humidity_threshold_advanced: bool = False,
        voc_threshold: ThresholdLevel | None = None,
        voc_threshold_advanced: bool = False,
        lux_threshold: ThresholdLevel | None = None,
        slave_rotation: SlaveRotation | None = None,
    ) -> bool:
        """Set humidity/VOC/lux sensor-mode thresholds and/or slave rotation.

        These fields share the same device register: any field left as `None` is
        preserved unchanged, so only pass the field(s) you actually want to change.

        NOTE: reverse-engineering on 2026-07-29 found that humidity/VOC/lux threshold
        changes did not reliably persist or read back via `sync/cronos400` (nor in the
        vendor app's own UI), suggesting a device/firmware-side issue rather than an API
        quirk. Do not build a stateful consumer (e.g. a Home Assistant entity) on top of
        the threshold fields without further verification. `slave_rotation` was confirmed
        reliable both ways.
        """
        return await self._set_advanced_settings(
            device_sn,
            humidity_threshold=humidity_threshold,
            humidity_threshold_advanced=humidity_threshold_advanced,
            voc_threshold=voc_threshold,
            voc_threshold_advanced=voc_threshold_advanced,
            lux_threshold=lux_threshold,
            slave_rotation=slave_rotation,
        )

    async def set_slave_rotation(self, device_sn: str, rotation: SlaveRotation) -> bool:
        """Set the direction of a slave unit relative to its master."""
        return await self.set_advanced_settings(device_sn, slave_rotation=rotation)


class IntelliClimaEcocomfort3API(_IntelliClimaVMCAPI):
    """API client for ECOCOMFORT 3 communication."""

    _endpoint_prefix = "eco3"

    async def set_advanced_settings(
        self,
        device_sn: str,
        *,
        humidity_threshold: ThresholdLevel | None = None,
        humidity_threshold_advanced: bool = False,
        co2_threshold: ThresholdLevel | None = None,
        co2_threshold_advanced: bool = False,
        lux_threshold: ThresholdLevel | None = None,
        slave_rotation: SlaveRotation | None = None,
    ) -> bool:
        """Set ECOCOMFORT 3 sensor thresholds and/or slave rotation."""
        return await self._set_advanced_settings(
            device_sn,
            humidity_threshold=humidity_threshold,
            humidity_threshold_advanced=humidity_threshold_advanced,
            voc_threshold=co2_threshold,
            voc_threshold_advanced=co2_threshold_advanced,
            lux_threshold=lux_threshold,
            slave_rotation=slave_rotation,
        )

    async def set_slave_rotation(self, device_sn: str, rotation: SlaveRotation) -> bool:
        """Set the direction of a slave unit relative to its master."""
        return await self.set_advanced_settings(device_sn, slave_rotation=rotation)

    async def set_season(self, device_sn: str, season: Season) -> bool:
        """Set winter/summer mode on an ECOCOMFORT 3 device."""
        command = create_season_free_cooling_command(device_sn, season=season)
        await post_to_session(
            self._session,
            "eco3/send/",
            headers=self._token_headers,
            json_payload={"trama": command},
        )
        await post_to_session(
            self._session,
            "eco3/setdata/",
            headers=self._token_headers,
            json_payload={"serial": device_sn, "data": json.dumps({"ws": int(season)})},
        )
        await asyncio.sleep(REFRESH_DELAY)
        return True

    async def set_free_cooling(self, device_sn: str, level: FreeCoolingLevel) -> bool:
        """Set the free-cooling level on an ECOCOMFORT 3 device."""
        command = create_season_free_cooling_command(device_sn, free_cooling=level)
        await post_to_session(
            self._session,
            "eco3/send/",
            headers=self._token_headers,
            json_payload={"trama": command},
        )
        await post_to_session(
            self._session,
            "eco3/freecoolset/",
            headers=self._token_headers,
            json_payload={"serial": device_sn, "value": int(level)},
        )
        await asyncio.sleep(REFRESH_DELAY)
        return True


class IntelliClimaAPI:
    """API client for IntelliClima."""

    def __init__(self, session: ClientSession, username: str, password: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self.auth_token: str | None = None
        self.user_id: str | None = None
        self.house_ids: list[str] = []
        self.device_id_types: dict[str, str] = {}
        self._mono_url = API_BASE_URL + API_MONO
        self._token_headers = {
            "TOKENID": "",
            "TOKEN": "",
        }
        self.ecocomfort = IntelliClimaEcocomfortAPI(self._session, self._token_headers)
        self.ecocomfort3 = IntelliClimaEcocomfort3API(self._session, self._token_headers)

    async def authenticate(self) -> bool:
        """Authenticate with the API."""
        try:
            hashed_password = hashlib.sha256(self._password.encode()).hexdigest()
            login_payload = asdict(
                IntelliClimaLoginBody(
                    manufacturer="Home Assistant",
                    model="HA Integration",
                    platform="Home Assistant IntelliClima",
                    version="1.0.0",
                    serial="unknown",
                    uuid=str(uuid.uuid4()),
                    language="english",
                )
            )

            LOGGER.info("Login with Intelliclima user: %s", self._username)
            LOGGER.debug("Login payload: %s", json.dumps(login_payload, indent=2))

            response = await post_to_session(
                self._session,
                f"user/login/{self._username}/{hashed_password}",
                json_payload=login_payload,
            )

            self.auth_token = response.get("token")
            self.user_id = response.get("id")

            if response.get("error") == "NO_PASSWORD":
                raise IntelliClimaAuthError("No or incorrect password")
            if not self.auth_token:
                raise IntelliClimaAuthError("No token in response")
            if not self.user_id:
                raise IntelliClimaAuthError("No user ID in response")

            await self.set_all_token_headers(
                {
                    "TOKENID": self.user_id,
                    "TOKEN": self.auth_token,
                }
            )

            await self.set_house_and_device_ids()

        except ClientError as err:
            LOGGER.error("Authentication failed: %s", err)
            raise IntelliClimaAuthError(f"Authentication failed: {err}") from err

        else:
            return True

    async def set_all_token_headers(self, token_headers: dict[str, Any]) -> None:
        """Sets main API token headers and child device API token headers."""
        self._token_headers = token_headers
        await self.ecocomfort.set_token_headers(token_headers)
        await self.ecocomfort3.set_token_headers(token_headers)

    async def get_all_device_status(
        self,
    ) -> IntelliClimaDevices:
        """Poll all devices."""
        device_ids_eco: list[str] = []
        device_ids_eco3: list[str] = []
        for device_id, device_type in self.device_id_types.items():
            if device_type == "ECO":
                device_ids_eco.append(str(device_id))
            elif device_type == "ECO3":
                device_ids_eco3.append(str(device_id))
            else:
                LOGGER.warning(
                    "Ignoring unsupported IntelliClima device type %s",
                    device_type,
                )

        devices_eco_string = ",".join(device_ids_eco)
        devices_eco3_string = ",".join(device_ids_eco3)
        get_device_body = {
            "IDs": "",
            "ECOs": devices_eco_string,
            "ECO3s": devices_eco3_string,
            "includi_eco": True,
            "includi_ledot": True,
            "includi_eco3": True,
        }
        LOGGER.debug(
            "Obtaining status for IntelliClima ECO devices: %s; ECO3 devices: %s",
            devices_eco_string,
            devices_eco3_string,
        )

        response = await post_to_session(
            self._session, "sync/cronos400", json_payload=get_device_body
        )

        # Parse 'model' and 'config' fields JSON strings to Python objects
        eco_devices: dict[str, IntelliClimaECO] = {}
        eco3_devices: dict[str, IntelliClimaECO3] = {}
        for device_data in response.get("data", []):
            try:
                device_data["model"] = json.loads(device_data.get("model", "{}"))
            except (KeyError, json.JSONDecodeError):
                device_data["model"] = device_data.get("model")

            try:
                device_data["config"] = json.loads(device_data.get("config", "{}"))
            except (KeyError, json.JSONDecodeError):
                device_data["config"] = device_data.get("config")

            # The low nibble contains the airflow mode. ECOCOMFORT devices may
            # set flags in the upper nibble (for example, ECOCOMFORT 3 has been
            # observed returning 20 for sensor mode: 0x10 | 0x04).
            mode_set = int(device_data["mode_set"]) & 0x0F
            device_data["mode_set"] = FanMode(str(mode_set))
            device_data["speed_set"] = FanSpeed(device_data["speed_set"])

            device_id = str(device_data["id"])
            if self.device_id_types.get(device_id) == "ECO3":
                eco3_device = from_dict(data_class=IntelliClimaECO3, data=device_data)
                eco3_devices[eco3_device.id] = eco3_device
            else:
                eco_device = from_dict(data_class=IntelliClimaECO, data=device_data)
                eco_devices[eco_device.id] = eco_device

        return IntelliClimaDevices(
            ecocomfort2_devices=eco_devices,
            c800_devices={},
            ecocomfort3_devices=eco3_devices,
        )

    async def _post_filter_action(
        self, serial: str, action: Literal["CALCULATE", "ACTIVATE", "DEACTIVATE", "RESET"]
    ) -> IntelliClimaFilterStatus:
        response = await post_to_session(
            self._session,
            "eco/filters/",
            headers=self._token_headers,
            json_payload={"serial": serial, "action": action},
        )
        return from_dict(data_class=IntelliClimaFilterStatus, data=response)

    async def get_filter_status(self, serial: str) -> IntelliClimaFilterStatus:
        """Calculate the current filter wear/cleaning status for a single device."""
        return await self._post_filter_action(serial, "CALCULATE")

    async def set_filter_tracking_active(
        self, serial: str, active: bool
    ) -> IntelliClimaFilterStatus:
        """Enable or disable filter wear tracking for a single device."""
        return await self._post_filter_action(serial, "ACTIVATE" if active else "DEACTIVATE")

    async def reset_filter_counter(self, serial: str) -> IntelliClimaFilterStatus:
        """Reset the accumulated filter wear counter for a single device."""
        return await self._post_filter_action(serial, "RESET")

    async def set_house_and_device_ids(self) -> None:
        """Finds the user's houses and their corresponding devices."""

        try:
            LOGGER.info(f"Obtaining IntelliClima house & devices for user: {self.user_id}")

            response = await post_to_session(
                self._session,
                f"casa/elenco3/{self.user_id}",
                headers=self._token_headers,
            )

            houses = response.get("houses", {})
            self.house_ids = list(houses.keys())
            self.device_id_types = {
                str(device.get("id")): device.get("tipo")
                for house_id in self.house_ids
                for device in houses[house_id]
                if device.get("tipo") != "CH"
            }
        except Exception as e:  # noqa: BLE001
            LOGGER.error(f"Error while getting houses for user: {self.user_id}: {e}")
