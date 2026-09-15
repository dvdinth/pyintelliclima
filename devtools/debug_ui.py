"""Local debug UI for driving the pyintelliclima API by hand.

Serves a page on localhost that logs in with real credentials, polls devices, sends
commands and builds command frames, so new library code can be exercised without going
through the Home Assistant integration. Every HTTP request and response the library
makes, plus its own log output, is streamed to the page.

    uv run python devtools/debug_ui.py --open

Credentials are kept in memory only; `INTELLICLIMA_USERNAME`/`INTELLICLIMA_PASSWORD`
prefill the login form when set.

USE AT YOUR OWN RISK. This is an unofficial tool for an undocumented, reverse-engineered
API. Commands sent from here reach real hardware and can change settings, clear counters
or unlink a satellite from its main unit, with no undo. It comes with no warranty of any
kind, and the author and contributors accept no responsibility for any damage, lost
settings or other consequences of using it.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import webbrowser
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, TypeVar

from aiohttp import (
    ClientSession,
    TraceConfig,
    TraceRequestChunkSentParams,
    TraceRequestEndParams,
    TraceRequestStartParams,
    web,
)
from typing_extensions import override

from pyintelliclima.api import (
    IntelliClimaAPI,
    IntelliClimaAPIError,
    IntelliClimaAuthError,
    IntelliClimaEcocomfort2API,
    IntelliClimaEcocomfort3API,
    create_advanced_settings_command,
    create_filter_reset_command,
    create_mode_speed_command,
    create_offsets_command,
    create_season_free_cooling_command,
    post_to_session,
)
from pyintelliclima.const import (
    API_MONO,
    FanMode,
    FanSpeed,
    FreeCoolingLevel,
    SatelliteRotation,
    Season,
    ThresholdLevel,
)
from pyintelliclima.intelliclima_types import IntelliClimaECO3, IntelliClimaVMCBase

HTML_PATH = Path(__file__).with_name("debug_ui.html")

DISCLAIMER = (
    "\n!! USE AT YOUR OWN RISK: this tool drives real hardware over an undocumented,\n"
    "   reverse-engineered API. Writes cannot be undone, and there is no warranty and\n"
    "   no liability for damaged devices or lost settings.\n"
)

# Bodies are shown verbatim in the page, and a status poll for several devices is large.
MAX_BODY_CHARS = 40000

VMCClient = IntelliClimaEcocomfort2API | IntelliClimaEcocomfort3API

E = TypeVar("E", bound=Enum)
N = TypeVar("N", int, float)


# ---- Log buffer ----


@dataclass(frozen=True)
class LogEntry:
    seq: int
    time: str
    kind: Literal["http", "log", "action"]
    level: str
    title: str
    detail: str


class DebugLog:
    """Ring buffer the page polls for new entries."""

    def __init__(self, maxlen: int = 500) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=maxlen)
        self._seq = 0

    def add(
        self,
        kind: Literal["http", "log", "action"],
        title: str,
        detail: str = "",
        level: str = "info",
    ) -> None:
        self._seq += 1
        self._entries.append(
            LogEntry(
                seq=self._seq,
                time=datetime.now().strftime("%H:%M:%S.%f")[:-3],
                kind=kind,
                level=level,
                title=title,
                detail=detail[:MAX_BODY_CHARS],
            )
        )

    def since(self, seq: int) -> list[LogEntry]:
        return [entry for entry in self._entries if entry.seq > seq]

    def clear(self) -> None:
        self._entries.clear()


class _BufferHandler(logging.Handler):
    """Feeds the library's own logging into the page."""

    def __init__(self, log: DebugLog) -> None:
        super().__init__(level=logging.DEBUG)
        self._log = log

    @override
    def emit(self, record: logging.LogRecord) -> None:
        detail = self.format(record) if record.exc_info else ""
        self._log.add("log", record.getMessage(), detail, level=record.levelname.lower())


def _pretty(text: str) -> str:
    if not text:
        return ""
    try:
        return json.dumps(json.loads(text), indent=2)
    except (json.JSONDecodeError, TypeError):
        return text


def _display_path(path: str) -> str:
    """Drop the constant API prefix, and never echo the password hash from a login URL."""
    short = path.removeprefix(API_MONO)
    parts = short.split("/")
    if short.startswith("user/login/") and len(parts) > 3:
        parts[3] = "<sha256>"
        short = "/".join(parts)
    return short


def make_trace_config(log: DebugLog) -> TraceConfig:
    """Log every request the library makes, with both bodies.

    Reading the response inside `on_request_end` is safe because aiohttp caches the
    body, so `post_to_session`'s own `resp.text()` still sees it.
    """
    trace = TraceConfig()

    async def on_request_start(
        session: ClientSession,  # pyright: ignore[reportUnusedParameter]
        context: SimpleNamespace,
        params: TraceRequestStartParams,  # pyright: ignore[reportUnusedParameter]
    ) -> None:
        context.started = time.monotonic()
        context.request_body = ""

    async def on_request_chunk_sent(
        session: ClientSession,  # pyright: ignore[reportUnusedParameter]
        context: SimpleNamespace,
        params: TraceRequestChunkSentParams,
    ) -> None:
        if not context.request_body:
            context.request_body = params.chunk.decode("utf-8", "replace")

    async def on_request_end(
        session: ClientSession,  # pyright: ignore[reportUnusedParameter]
        context: SimpleNamespace,
        params: TraceRequestEndParams,
    ) -> None:
        elapsed = (time.monotonic() - context.started) * 1000
        try:
            body = await params.response.text()
        except Exception as err:  # noqa: BLE001 - logging must never break the call
            body = f"<could not read body: {err}>"
        request_body = _pretty(str(context.request_body))
        detail = f"request:\n{request_body}\n\n" if request_body else ""
        log.add(
            "http",
            f"{params.method} {_display_path(params.url.path)} -> "
            f"{params.response.status} ({elapsed:.0f} ms)",
            f"{detail}response:\n{_pretty(body)}",
            level="info" if params.response.status < 400 else "error",
        )

    trace.on_request_start.append(on_request_start)
    trace.on_request_chunk_sent.append(on_request_chunk_sent)
    trace.on_request_end.append(on_request_end)
    return trace


# ---- Action metadata, rendered into forms by the page ----


@dataclass(frozen=True)
class Param:
    name: str
    kind: Literal["enum", "bool", "float", "int", "text"]
    choices: tuple[str, ...] = ()
    default: str = ""
    optional: bool = False


@dataclass(frozen=True)
class Action:
    name: str
    label: str
    params: tuple[Param, ...] = ()
    help: str = ""
    danger: str = ""


def _names(enum_cls: type[Enum]) -> tuple[str, ...]:
    """Enum member names, which is what the page shows and sends back."""
    return tuple(member.name for member in enum_cls)


def _threshold_params(gas: str) -> tuple[Param, ...]:
    """The shared register's fields, with `gas` being voc_threshold or co2_threshold."""
    return (
        Param("humidity_threshold", "enum", _names(ThresholdLevel), optional=True),
        Param("humidity_threshold_advanced", "bool"),
        Param(gas, "enum", _names(ThresholdLevel), optional=True),
        Param(f"{gas}_advanced", "bool"),
        Param("lux_threshold", "enum", _names(ThresholdLevel), optional=True),
        Param("satellite_rotation", "enum", _names(SatelliteRotation), optional=True),
    )


_COMMON_ACTIONS: tuple[Action, ...] = (
    Action(
        "set_mode_speed",
        "Set mode + speed",
        (
            Param("mode", "enum", _names(FanMode), default="inward"),
            Param("speed", "enum", _names(FanSpeed), default="low"),
        ),
    ),
    Action("set_mode_speed_auto", "Set auto (sensor mode)"),
    Action("turn_off", "Turn off"),
    Action(
        "set_season",
        "Set season",
        (Param("season", "enum", _names(Season), default="winter"),),
        help="Switching to winter also clears free cooling, as the vendor app does.",
    ),
    Action(
        "set_free_cooling",
        "Set free cooling",
        (Param("level", "enum", _names(FreeCoolingLevel), default="off"),),
        help="Only effective in summer mode.",
    ),
    Action(
        "set_temperature_and_humidity_offsets",
        "Set calibration offsets",
        (
            Param("temperature_offset", "float", default="0"),
            Param("humidity_offset", "int", default="0"),
        ),
        help="Both share one register, so both are always written - pass the current "
        "value for the one you are not changing.",
    ),
    Action(
        "set_satellite_rotation",
        "Set satellite rotation",
        (Param("rotation", "enum", _names(SatelliteRotation), default="concordant"),),
    ),
    Action("get_filter_status", "Get filter status"),
    Action(
        "set_filter_tracking_active",
        "Set filter tracking",
        (Param("active", "bool", default="1"),),
    ),
    Action(
        "reset_filter_counter",
        "Reset filter counter",
        danger="Clears the accumulated wear counter for this device.",
    ),
)


def actions_for(family: str) -> list[Action]:
    """The action list for one device family, named for that family's gas sensor."""
    gas = "co2_threshold" if family == "eco3" else "voc_threshold"
    advanced = Action(
        "set_advanced_settings",
        "Set advanced settings",
        _threshold_params(gas),
        help="Fields left empty are preserved on the device. Prefilled from the "
        "decoded values, never from the raw registers.",
    )
    return [*_COMMON_ACTIONS, advanced]


FRAME_BUILDERS: tuple[Action, ...] = (
    Action(
        "mode_speed",
        "create_mode_speed_command",
        (
            Param("mode", "enum", _names(FanMode), default="inward"),
            Param("speed", "enum", _names(FanSpeed), default="low"),
        ),
    ),
    Action(
        "offsets",
        "create_offsets_command",
        (
            Param("temperature_offset", "float", default="0"),
            Param("humidity_offset", "int", default="0"),
        ),
    ),
    Action(
        "advanced_settings",
        "create_advanced_settings_command",
        _threshold_params("voc_threshold"),
    ),
    Action(
        "season_free_cooling",
        "create_season_free_cooling_command",
        (
            Param("season", "enum", _names(Season), optional=True),
            Param("free_cooling", "enum", _names(FreeCoolingLevel), optional=True),
        ),
    ),
    Action("filter_reset", "create_filter_reset_command"),
)


# ---- Parameter coercion ----


def _enum_value(
    values: dict[str, Any], key: str, enum_cls: type[E], *, optional: bool = False
) -> E | None:
    raw = str(values.get(key) or "").strip()
    if not raw:
        if optional:
            return None
        raise web.HTTPBadRequest(text=f"Missing value for {key}")
    try:
        return enum_cls[raw]
    except KeyError:
        raise web.HTTPBadRequest(text=f"Unknown {key}: {raw!r}") from None


def _required_enum(values: dict[str, Any], key: str, enum_cls: type[E]) -> E:
    value = _enum_value(values, key, enum_cls)
    assert value is not None
    return value


def _bool_value(values: dict[str, Any], key: str) -> bool:
    return str(values.get(key) or "").strip().lower() in {"1", "true", "on", "yes"}


def _number(values: dict[str, Any], key: str, cast: Callable[[str], N]) -> N:
    raw = str(values.get(key) or "").strip() or "0"
    try:
        return cast(raw)
    except ValueError:
        raise web.HTTPBadRequest(text=f"{key} must be a number, got {raw!r}") from None


# ---- Server state ----


@dataclass
class DebugState:
    log: DebugLog = field(default_factory=DebugLog)
    session: ClientSession | None = None
    api: IntelliClimaAPI | None = None
    devices: dict[str, IntelliClimaVMCBase] = field(default_factory=dict)

    def require_api(self) -> IntelliClimaAPI:
        if self.api is None:
            raise web.HTTPBadRequest(text="Not logged in")
        return self.api

    def require_session(self) -> ClientSession:
        if self.session is None:
            raise web.HTTPBadRequest(text="Not logged in")
        return self.session

    def require_device(self, device_id: str) -> IntelliClimaVMCBase:
        device = self.devices.get(device_id)
        if device is None:
            raise web.HTTPBadRequest(text=f"Unknown device {device_id!r}; poll first")
        return device

    def client_for(self, device: IntelliClimaVMCBase) -> VMCClient:
        api = self.require_api()
        return api.ecocomfort3 if isinstance(device, IntelliClimaECO3) else api.ecocomfort2

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()
        self.session = None
        self.api = None
        self.devices = {}


def _get_state(request: web.Request) -> DebugState:
    state = request.app["state"]
    assert isinstance(state, DebugState)
    return state


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.name
    return str(value)


def _json_response(payload: Any, status: int = 200) -> web.Response:
    return web.json_response(
        payload, status=status, dumps=lambda obj: json.dumps(obj, default=_json_default)
    )


def _family(device: IntelliClimaVMCBase) -> str:
    return "eco3" if isinstance(device, IntelliClimaECO3) else "eco"


def _decoded(device: IntelliClimaVMCBase) -> dict[str, Any]:
    """The library's decoded views of the raw registers, errors included rather than raised."""
    decoded: dict[str, Any] = {}
    names = ("fan_state", "humidity_threshold", "luminosity_threshold")
    names += ("co2_threshold",) if isinstance(device, IntelliClimaECO3) else ("voc_threshold",)
    for name in names:
        try:
            value: Any = getattr(device, name)
        except ValueError as err:
            decoded[name] = f"decode error: {err}"
            continue
        decoded[name] = (
            asdict(value) if is_dataclass(value) and not isinstance(value, type) else value
        )
    return decoded


def _describe(device: IntelliClimaVMCBase) -> dict[str, Any]:
    """Everything the page shows for one device: identity, headline values, decoded, raw."""
    return {
        "id": device.id,
        "serial": device.crono_sn,
        "name": device.name,
        "family": _family(device),
        "model": device.model.modello,
        "online": device.online_status,
        "role": "main" if device.role == "1" else "satellite",
        "summary": {
            "temperature": device.tamb,
            "humidity": device.rh,
            "voc_state": device.voc_state,
            "co2": device.co2,
            "aqi": device.aqi,
            "season": Season(device.ws).name if device.ws in {"0", "1"} else device.ws,
            "free_cooling": device.fcool,
            "mode_set": device.mode_set.name,
            "speed_set": device.speed_set.name,
            "mode_state": device.mode_state,
            "speed_state": device.speed_state,
            "dev_state": device.dev_state,
            "filter_active": device.filter_active,
            "fw": device.fw,
            "rssi": device.rssi,
            "last_online": device.last_online,
        },
        "decoded": _decoded(device),
        "raw": asdict(device),
    }


# ---- Action dispatch ----


async def _run_action(client: VMCClient, serial: str, name: str, values: dict[str, Any]) -> Any:
    match name:
        case "turn_off":
            return await client.turn_off(serial)
        case "set_mode_speed":
            return await client.set_mode_speed(
                serial,
                mode=_required_enum(values, "mode", FanMode),
                speed=_required_enum(values, "speed", FanSpeed),
            )
        case "set_mode_speed_auto":
            return await client.set_mode_speed_auto(serial)
        case "set_temperature_and_humidity_offsets":
            return await client.set_temperature_and_humidity_offsets(
                serial,
                _number(values, "temperature_offset", float),
                _number(values, "humidity_offset", int),
            )
        case "set_season":
            return await client.set_season(serial, _required_enum(values, "season", Season))
        case "set_free_cooling":
            return await client.set_free_cooling(
                serial, _required_enum(values, "level", FreeCoolingLevel)
            )
        case "set_satellite_rotation":
            return await client.set_satellite_rotation(
                serial, _required_enum(values, "rotation", SatelliteRotation)
            )
        case "get_filter_status":
            return asdict(await client.get_filter_status(serial))
        case "set_filter_tracking_active":
            return asdict(
                await client.set_filter_tracking_active(serial, _bool_value(values, "active"))
            )
        case "reset_filter_counter":
            return asdict(await client.reset_filter_counter(serial))
        case "set_advanced_settings":
            return await _run_advanced_settings(client, serial, values)
        case _:
            raise web.HTTPBadRequest(text=f"Unknown action {name!r}")


async def _run_advanced_settings(client: VMCClient, serial: str, values: dict[str, Any]) -> bool:
    """Dispatch on the concrete client: the gas threshold kwarg differs per generation."""
    humidity = _enum_value(values, "humidity_threshold", ThresholdLevel, optional=True)
    humidity_advanced = _bool_value(values, "humidity_threshold_advanced")
    lux = _enum_value(values, "lux_threshold", ThresholdLevel, optional=True)
    rotation = _enum_value(values, "satellite_rotation", SatelliteRotation, optional=True)

    if isinstance(client, IntelliClimaEcocomfort3API):
        return await client.set_advanced_settings(
            serial,
            humidity_threshold=humidity,
            humidity_threshold_advanced=humidity_advanced,
            co2_threshold=_enum_value(values, "co2_threshold", ThresholdLevel, optional=True),
            co2_threshold_advanced=_bool_value(values, "co2_threshold_advanced"),
            lux_threshold=lux,
            satellite_rotation=rotation,
        )
    return await client.set_advanced_settings(
        serial,
        humidity_threshold=humidity,
        humidity_threshold_advanced=humidity_advanced,
        voc_threshold=_enum_value(values, "voc_threshold", ThresholdLevel, optional=True),
        voc_threshold_advanced=_bool_value(values, "voc_threshold_advanced"),
        lux_threshold=lux,
        satellite_rotation=rotation,
    )


def _build_frame(builder: str, serial: str, values: dict[str, Any]) -> str:
    match builder:
        case "mode_speed":
            return create_mode_speed_command(
                serial,
                _required_enum(values, "mode", FanMode),
                _required_enum(values, "speed", FanSpeed),
            )
        case "offsets":
            return create_offsets_command(
                serial,
                _number(values, "temperature_offset", float),
                _number(values, "humidity_offset", int),
            )
        case "advanced_settings":
            return create_advanced_settings_command(
                serial,
                humidity_threshold=_enum_value(
                    values, "humidity_threshold", ThresholdLevel, optional=True
                ),
                humidity_threshold_advanced=_bool_value(values, "humidity_threshold_advanced"),
                voc_threshold=_enum_value(values, "voc_threshold", ThresholdLevel, optional=True),
                voc_threshold_advanced=_bool_value(values, "voc_threshold_advanced"),
                lux_threshold=_enum_value(values, "lux_threshold", ThresholdLevel, optional=True),
                satellite_rotation=_enum_value(
                    values, "satellite_rotation", SatelliteRotation, optional=True
                ),
            )
        case "season_free_cooling":
            return create_season_free_cooling_command(
                serial,
                season=_enum_value(values, "season", Season, optional=True),
                free_cooling=_enum_value(values, "free_cooling", FreeCoolingLevel, optional=True),
            )
        case "filter_reset":
            return create_filter_reset_command(serial)
        case _:
            raise web.HTTPBadRequest(text=f"Unknown builder {builder!r}")


# ---- Handlers ----


async def handle_index(request: web.Request) -> web.Response:  # pyright: ignore[reportUnusedParameter]
    return web.Response(text=HTML_PATH.read_text(), content_type="text/html")


async def handle_state(request: web.Request) -> web.Response:
    api = _get_state(request).api
    return _json_response(
        {
            "logged_in": api is not None,
            "user_id": api.user_id if api else None,
            "house_ids": api.house_ids if api else [],
            "eco_ids": api.ecocomfort2_ids if api else [],
            "eco3_ids": api.ecocomfort3_ids if api else [],
            "prefill_username": os.environ.get("INTELLICLIMA_USERNAME", ""),
            "prefill_password": os.environ.get("INTELLICLIMA_PASSWORD", ""),
        }
    )


async def handle_login(request: web.Request) -> web.Response:
    state = _get_state(request)
    body = await request.json()
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    if not username or not password:
        raise web.HTTPBadRequest(text="Username and password are required")

    await state.close()
    state.session = ClientSession(trace_configs=[make_trace_config(state.log)])
    state.api = IntelliClimaAPI(state.session, username, password)
    state.log.add("action", f"authenticate({username})")
    try:
        await state.api.authenticate()
    except (IntelliClimaAuthError, IntelliClimaAPIError, OSError) as err:
        state.log.add("action", f"login failed: {err}", level="error")
        await state.close()
        return _json_response({"error": str(err)}, status=400)
    return await handle_state(request)


async def handle_logout(request: web.Request) -> web.Response:
    state = _get_state(request)
    await state.close()
    state.log.add("action", "logged out")
    return await handle_state(request)


async def handle_poll(request: web.Request) -> web.Response:
    state = _get_state(request)
    api = state.require_api()
    state.log.add("action", "get_all_device_status()")
    devices = await api.get_all_device_status()
    state.devices = {**devices.ecocomfort2_devices, **devices.ecocomfort3_devices}
    return _json_response({"devices": [_describe(d) for d in state.devices.values()]})


async def handle_actions(request: web.Request) -> web.Response:  # pyright: ignore[reportUnusedParameter]
    return _json_response(
        {
            "eco": [asdict(action) for action in actions_for("eco")],
            "eco3": [asdict(action) for action in actions_for("eco3")],
            "frames": [asdict(action) for action in FRAME_BUILDERS],
        }
    )


async def handle_command(request: web.Request) -> web.Response:
    state = _get_state(request)
    body = await request.json()
    device = state.require_device(str(body.get("device_id", "")))
    client = state.client_for(device)
    name = str(body.get("action", ""))
    values: dict[str, Any] = body.get("params") or {}

    state.log.add("action", f"{name}({device.name} / {device.crono_sn}) {values}")
    try:
        result = await _run_action(client, device.crono_sn, name, values)
    except (IntelliClimaAPIError, OSError) as err:
        state.log.add("action", f"{name} failed: {err}", level="error")
        return _json_response({"error": str(err)}, status=400)
    return _json_response({"result": result})


async def handle_frame(request: web.Request) -> web.Response:
    """Build a command frame and return its hex without sending it."""
    state = _get_state(request)
    body = await request.json()
    serial = str(body.get("serial", "")).strip()
    if not serial:
        raise web.HTTPBadRequest(text="Serial is required")
    builder = str(body.get("builder", ""))
    values: dict[str, Any] = body.get("params") or {}

    try:
        frame = _build_frame(builder, serial, values)
    except (ValueError, TypeError) as err:
        return _json_response({"error": f"{type(err).__name__}: {err}"}, status=400)

    state.log.add("action", f"{builder} frame for {serial}: {frame}")
    return _json_response({"frame": frame})


async def handle_send_frame(request: web.Request) -> web.Response:
    """Send a hand-written frame to `eco/send/` or `eco3/send/`."""
    state = _get_state(request)
    api = state.require_api()
    body = await request.json()
    frame = str(body.get("frame", "")).strip().upper()
    if not frame:
        raise web.HTTPBadRequest(text="Frame is required")
    prefix = "eco3" if str(body.get("family", "eco")) == "eco3" else "eco"

    state.log.add("action", f"send {prefix} frame: {frame}")
    try:
        response = await post_to_session(
            state.require_session(),
            f"{prefix}/send/",
            headers={"TOKENID": api.user_id, "TOKEN": api.auth_token},
            json_payload={"trama": frame},
        )
    except (IntelliClimaAPIError, OSError) as err:
        return _json_response({"error": str(err)}, status=400)
    return _json_response({"result": response})


async def handle_raw(request: web.Request) -> web.Response:
    """POST an arbitrary endpoint, for probing parts of the API the library has no call for."""
    state = _get_state(request)
    api = state.require_api()
    body = await request.json()
    path = str(body.get("path", "")).strip().lstrip("/")
    if not path:
        raise web.HTTPBadRequest(text="Path is required")
    payload_text = str(body.get("payload", "") or "").strip()
    try:
        payload = json.loads(payload_text) if payload_text else None
    except json.JSONDecodeError as err:
        return _json_response({"error": f"Payload is not valid JSON: {err}"}, status=400)

    headers = None
    if body.get("authenticated", True):
        headers = {"TOKENID": api.user_id, "TOKEN": api.auth_token}

    state.log.add("action", f"raw POST {path}")
    try:
        response = await post_to_session(
            state.require_session(),
            path,
            headers=headers,
            json_payload=payload,
            raise_on_status=bool(body.get("raise_on_status", False)),
        )
    except (IntelliClimaAPIError, OSError) as err:
        return _json_response({"error": str(err)}, status=400)
    return _json_response({"result": response})


async def handle_log(request: web.Request) -> web.Response:
    state = _get_state(request)
    try:
        since = int(request.query.get("since", "0"))
    except ValueError:
        since = 0
    return _json_response({"entries": [asdict(entry) for entry in state.log.since(since)]})


async def handle_log_clear(request: web.Request) -> web.Response:
    _get_state(request).log.clear()
    return _json_response({"ok": True})


@web.middleware
async def error_middleware(
    request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
) -> web.StreamResponse:
    """Turn an unexpected failure into JSON, so a bad guess while probing never kills the server."""
    try:
        return await handler(request)
    except web.HTTPException as err:
        if err.status >= 400:
            _get_state(request).log.add("action", f"{err.status}: {err.text}", level="error")
            return _json_response({"error": err.text}, status=err.status)
        raise
    except Exception as err:  # noqa: BLE001 - a debug tool must stay up
        _get_state(request).log.add("action", f"{type(err).__name__}: {err}", level="error")
        logging.getLogger(__name__).exception("Unhandled error in %s", request.path)
        return _json_response({"error": f"{type(err).__name__}: {err}"}, status=500)


def build_app() -> web.Application:
    state = DebugState()
    library_logger = logging.getLogger("pyintelliclima")
    library_logger.setLevel(logging.DEBUG)
    library_logger.addHandler(_BufferHandler(state.log))

    app = web.Application(middlewares=[error_middleware])
    app["state"] = state
    app.add_routes(
        [
            web.get("/", handle_index),
            web.get("/api/state", handle_state),
            web.post("/api/login", handle_login),
            web.post("/api/logout", handle_logout),
            web.post("/api/poll", handle_poll),
            web.get("/api/actions", handle_actions),
            web.post("/api/command", handle_command),
            web.post("/api/frame", handle_frame),
            web.post("/api/send_frame", handle_send_frame),
            web.post("/api/raw", handle_raw),
            web.get("/api/log", handle_log),
            web.post("/api/log/clear", handle_log_clear),
        ]
    )

    async def on_cleanup(app: web.Application) -> None:
        await _get_state_from_app(app).close()

    app.on_cleanup.append(on_cleanup)
    return app


def _get_state_from_app(app: web.Application) -> DebugState:
    state = app["state"]
    assert isinstance(state, DebugState)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Local debug UI for the IntelliClima API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="open the page in a browser")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    url = f"http://{args.host}:{args.port}/"
    print(f"IntelliClima debug UI on {url}")
    print(DISCLAIMER)

    app = build_app()
    if args.open:
        # The browser races the server here, but aiohttp binds before the page loads.
        app.on_startup.append(lambda _app: _open_browser(url))

    web.run_app(app, host=args.host, port=args.port, print=None)


async def _open_browser(url: str) -> None:
    webbrowser.open(url)


if __name__ == "__main__":
    main()
