"""API client for IntelliClima integration."""

import binascii
import hashlib
import json
import logging
import uuid
from dataclasses import asdict
from typing import Any, Literal

from aiohttp import ClientError, ClientSession
from dacite import from_dict

from .const import API_BASE_URL, API_MONO
from .intelliclima_types import (
    IntelliClimaDevices,
    IntelliClimaECO,
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


def checksum_crc8_nrsc5(data_bytes: bytearray, poly: Literal[49] = 0x31, init: Literal[255] = 0xFF):
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


def create_mode_speed_command(device_sn: str, mode: str, speed: str) -> str:
    """Creates the api request command that sets mode and speed for a certain device."""
    LOGGER.debug(
        "Setting mode & speed for device %s to mode: %s, speed %s",
        device_sn,
        mode,
        speed,
    )
    partial_command = "0A" + device_sn + "000E2F00500000" + f"{int(mode):02d}" + f"{int(speed):02d}"
    base_data = bytearray(hex_to_bytes(partial_command))
    base_data.append(0x00)  # Placeholder for checksum
    base_data.append(0x0D)  # Termination byte

    cs = checksum_crc8_nrsc5(base_data[1:-2])
    base_data[-2] = cs  # Set checksum byte

    return bytes_to_hex(base_data).upper()


class IntelliClimaAPIError(Exception):
    """Exception for API errors."""


class IntelliClimaAuthError(IntelliClimaAPIError):
    """Exception for authentication errors."""


class IntelliClimaEcocomfortAPI:
    """API client for specific ECOCOMFORT 2.0 communication."""

    def __init__(self, session: ClientSession, token_headers: dict[str, Any]) -> None:
        """Initialize the ECOCOMFORT API client."""
        self._session = session
        self._token_headers = token_headers

    async def set_token_headers(self, token_headers: dict[str, Any]) -> None:
        """Sets the ECOCOMFORT 2.0 API token headers."""
        self._token_headers = token_headers

    async def turn_off(self, device_sn: str) -> bool:
        """Turn off an ECOCOMFORT 2.0 device."""
        return await self.set_mode_speed(device_sn, mode="00", speed="00")

    async def set_mode_speed(self, device_sn: str, mode: str, speed: str) -> bool:
        """Set the mode and speed of an ecocomfort device."""
        command = create_mode_speed_command(device_sn, mode, speed)
        payload = {"trama": command}
        LOGGER.debug(
            "Sending command: %s",
            command,
        )
        response = await post_to_session(
            self._session,
            "eco/send/",
            headers=self._token_headers,
            json_payload=payload,
        )

        status = response.get("status")
        if status != "OK":
            msg = f"Setting mode and speed did not succeed with status: {status}"
            raise IntelliClimaAPIError(msg)

        return True

    async def set_mode_speed_auto(self, device_sn: str) -> bool:
        """Set the auto preset mode and speed."""
        return await self.set_mode_speed(device_sn, mode="04", speed="10")


class IntelliClimaAPI:
    """API client for IntelliClima."""

    def __init__(self, session: ClientSession, username: str, password: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self.auth_token: str | None = None
        self.user_id: str | None = None
        self.house_id: str | None = None
        self.device_id_types: dict[str, str] = {}
        self._mono_url = API_BASE_URL + API_MONO
        self._token_headers = {
            "TOKENID": "",
            "TOKEN": "",
        }
        self.ecocomfort = IntelliClimaEcocomfortAPI(self._session, self._token_headers)

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

    async def get_all_device_status(
        self,
    ) -> IntelliClimaDevices:
        """Poll all devices."""
        device_ids_eco: list[str] = []
        for device_id, device_type in self.device_id_types.items():
            if device_type == "ECO":
                device_ids_eco.append(str(device_id))
            else:
                LOGGER.warning(
                    "Only ECOCOMFORT 2.0 is implemented at this moment! Ignoring device %s",
                    device_type,
                )

        devices_eco_string = ",".join(device_ids_eco)
        get_device_body = {
            "IDs": "",
            "ECOs": devices_eco_string,
            "includi_eco": True,
            "includi_ledot": True,
        }
        LOGGER.debug("Obtaining status for Intelliclima devices: %s", devices_eco_string)

        response = await post_to_session(
            self._session, "sync/cronos400", json_payload=get_device_body
        )

        # Parse 'model' and 'config' fields JSON strings to Python objects
        eco_devices: dict[str, IntelliClimaECO] = {}
        for device_data in response.get("data", []):
            try:
                device_data["model"] = json.loads(device_data.get("model", "{}"))
            except (KeyError, json.JSONDecodeError):
                device_data["model"] = device_data.get("model")

            try:
                device_data["config"] = json.loads(device_data.get("config", "{}"))
            except (KeyError, json.JSONDecodeError):
                device_data["config"] = device_data.get("config")

            eco_device = from_dict(data_class=IntelliClimaECO, data=device_data)
            eco_devices[eco_device.id] = eco_device

        return IntelliClimaDevices(ecocomfort2_devices=eco_devices, c800_devices={})

    async def set_house_and_device_ids(self) -> None:
        """Finds the user's house ID and corresponding devices."""

        try:
            LOGGER.info(f"Obtaining IntelliClima house & devices for user: {self.user_id}")

            response = await post_to_session(
                self._session,
                f"casa/elenco3/{self.user_id}",
                headers=self._token_headers,
            )

            houses = response.get("houses", {})
            if houses:
                self.house_id = list(houses.keys())[0]
                self.device_id_types = {
                    str(device.get("id")): device.get("tipo")
                    for device in houses[self.house_id]
                    if device.get("tipo") != "CH"
                }
        except Exception as e:  # noqa: BLE001
            LOGGER.error(f"Error while getting houses for user: {self.user_id}: {e}")
