import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import IntelliClimaAPI
from pyintelliclima.const import FanMode
from pyintelliclima.intelliclima_types import (
    IntelliClimaDevices,
    IntelliClimaECO2,
    IntelliClimaECO3,
    IntelliClimaVMCBase,
)

pytestmark = pytest.mark.asyncio


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_get_all_device_status_basic(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.device_id_types = {"10": "ECO", "11": "C800"}

    device_data = {
        "id": "10",
        "crono_sn": "SN",
        "status": "1",
        "online": "1",
        "command": "",
        "model": json.dumps({"modello": "ECO", "tipo": "ECOCOMFORT"}),
        "name": "Device 10",
        "houses_id": "1",
        "mode_set": "0",
        "mode_state": "0",
        "speed_set": "0",
        "speed_state": "0",
        "last_online": "",
        "creation_date": "",
        "fw": "",
        "mac": "",
        "macwifi": "",
        "conn_num": "",
        "conn_state": "",
        "role": "1",
        "rh_thrs": "",
        "lux_thrs": "",
        "voc_thrs": "",
        "slv_rot": "",
        "slv_addr": "",
        "offset_temp": "",
        "offset_hum": "",
        "year": "",
        "month": "",
        "day": "",
        "dow": "",
        "hour": "",
        "minute": "",
        "second": "",
        "dst": "",
        "mode_prev": None,
        "dir_state": "",
        "auto_cycle": "",
        "tamb": "",
        "rh": "",
        "voc_state": "",
        "plun": json.dumps({"w": [0], "s": [0]}),
        "pmar": json.dumps({"w": [0], "s": [0]}),
        "pmer": json.dumps({"w": [0], "s": [0]}),
        "pgio": json.dumps({"w": [0], "s": [0]}),
        "pven": json.dumps({"w": [0], "s": [0]}),
        "psab": json.dumps({"w": [0], "s": [0]}),
        "pdom": json.dumps({"w": [0], "s": [0]}),
        "pcustom": None,
        "sfondo": "",
        "tperc": None,
        "fcool": "",
        "ws": "",
        "filter_from": "",
        "filter_active": "",
        "timezone": None,
        "co2": None,
        "sanification": None,
        "rssi": None,
        "aqi": None,
        "co2_thrs": None,
        "dev_state": None,
        "online_status": True,
        "online_status_debug": "",
        "config": json.dumps({"foo": "bar"}),
    }
    mock_post.return_value = {
        "status": "OK",
        "data": [device_data],
    }

    devices = await api.get_all_device_status()

    assert isinstance(devices, IntelliClimaDevices)
    assert devices.num_devices == 1
    assert "10" in devices.ecocomfort2_devices
    eco = devices.ecocomfort2_devices["10"]
    assert eco.id == "10"
    assert eco.model.modello == "ECO"
    assert eco.model.tipo == "ECOCOMFORT"
    assert eco.online_status is True


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_get_all_device_status_eco3(mock_post, caplog):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.device_id_types = {"30": "ECO3"}

    fixture_path = Path(__file__).parent / "fixtures" / "ecocomfort3_status.json"
    mock_post.return_value = json.loads(fixture_path.read_text())

    devices = await api.get_all_device_status()

    assert isinstance(devices, IntelliClimaDevices)
    assert devices.num_devices == 1
    assert devices.ecocomfort2_devices == {}
    assert "30" in devices.ecocomfort3_devices
    eco3 = devices.ecocomfort3_devices["30"]
    assert isinstance(eco3, IntelliClimaECO3)
    assert eco3.model.modello == "ECO3"
    assert eco3.fw == "0.9.6"
    assert eco3.voc_thrs is None
    assert eco3.mode_set is FanMode.sensor
    assert eco3.co2 == "510"
    assert eco3.voc_state == "750"
    assert eco3.aqi == "3"
    assert "unsupported" not in caplog.text

    request_body = mock_post.call_args.kwargs["json_payload"]
    assert request_body["ECO3s"] == "30"
    assert request_body["ECOs"] == ""
    assert request_body["includi_eco3"] is True


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_get_all_device_status_requests_eco2_and_eco3_together(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.device_id_types = {"10": "ECO", "30": "ECO3"}

    fixture_path = Path(__file__).parent / "fixtures" / "ecocomfort3_status.json"
    eco3_response = json.loads(fixture_path.read_text())
    eco_device = dict(eco3_response["data"][0])
    eco_device["id"] = "10"
    eco_device["model"] = json.dumps({"modello": "ECO", "tipo": "ECOCOMFORT"})
    mock_post.return_value = {
        "status": "OK",
        "data": [eco_device, *eco3_response["data"]],
    }

    devices = await api.get_all_device_status()

    assert devices.num_devices == 2
    assert isinstance(devices.ecocomfort2_devices["10"], IntelliClimaECO2)
    assert isinstance(devices.ecocomfort2_devices["10"], IntelliClimaVMCBase)
    assert not isinstance(devices.ecocomfort2_devices["10"], IntelliClimaECO3)
    assert isinstance(devices.ecocomfort3_devices["30"], IntelliClimaECO3)
    assert isinstance(devices.ecocomfort3_devices["30"], IntelliClimaVMCBase)
    assert not isinstance(devices.ecocomfort3_devices["30"], IntelliClimaECO2)
    request_body = mock_post.call_args.kwargs["json_payload"]
    assert request_body["ECOs"] == "10"
    assert request_body["ECO3s"] == "30"


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_get_all_device_status_skips_unsupported_types(mock_post, caplog):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.device_id_types = {"40": "C900", "50": "RHINO"}
    mock_post.return_value = {"status": "OK", "data": []}

    devices = await api.get_all_device_status()

    assert devices.num_devices == 0
    assert "C900" in caplog.text
    assert "RHINO" in caplog.text


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_get_all_device_status_isolates_unparsable_devices(mock_post, caplog):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.device_id_types = {"10": "ECO", "11": "ECO", "30": "ECO3"}

    fixture_path = Path(__file__).parent / "fixtures" / "ecocomfort3_status.json"
    eco3_response = json.loads(fixture_path.read_text())

    # A 'model' that isn't JSON reaches dacite as a plain string and fails the
    # IntelliClimaModelType field; an unknown speed is rejected by the enum. The two
    # raise from different libraries, so both paths are worth covering.
    bad_model = dict(eco3_response["data"][0])
    bad_model["id"] = "10"
    bad_model["model"] = "not-json"
    bad_speed = dict(eco3_response["data"][0])
    bad_speed["id"] = "11"
    bad_speed["speed_set"] = "99"

    mock_post.return_value = {
        "status": "OK",
        "data": [bad_model, bad_speed, *eco3_response["data"]],
    }

    devices = await api.get_all_device_status()

    assert devices.num_devices == 1
    assert devices.ecocomfort2_devices == {}
    assert "30" in devices.ecocomfort3_devices
    assert "Skipping IntelliClima device 10" in caplog.text
    assert "Skipping IntelliClima device 11" in caplog.text
