import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dacite import WrongTypeError

from pyintelliclima.api import IntelliClimaAPI
from pyintelliclima.intelliclima_types import IntelliClimaDevices

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
        "mode_set": "00",
        "mode_state": "00",
        "speed_set": "00",
        "speed_state": "00",
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
async def test_get_all_device_status_invalid_json_falls_back(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.device_id_types = {"10": "ECO"}

    device_data = {
        "id": "10",
        "crono_sn": "SN",
        "status": "1",
        "online": "1",
        "command": "",
        "model": "not-json",
        "name": "Device 10",
        "houses_id": "1",
        "mode_set": "00",
        "mode_state": "00",
        "speed_set": "00",
        "speed_state": "00",
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
        "config": "not-json",
    }
    mock_post.return_value = {
        "status": "OK",
        "data": [device_data],
    }

    with pytest.raises(WrongTypeError):
        await api.get_all_device_status()
