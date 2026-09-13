import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import IntelliClimaAPI, IntelliClimaAPIError

pytestmark = pytest.mark.asyncio


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_house_and_device_ids_reads_eco_id_arrays(mock_post, caplog):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.user_id = "user-id"

    # `tipo` is deliberately wrong here: the vendor app never reads it, and neither do we.
    mock_post.return_value = {
        "status": "OK",
        "houses": {
            "1": [
                {"id": "10", "tipo": "NONSENSE"},
                {"id": "30", "tipo": "NONSENSE"},
            ]
        },
        "ecoIDs": ["10"],
        "eco3IDs": ["30"],
    }

    await api.set_house_and_device_ids()

    assert api.house_ids == ["1"]
    assert api.ecocomfort2_ids == ["10"]
    assert api.ecocomfort3_ids == ["30"]
    assert "Error while getting houses" not in caplog.text


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_house_and_device_ids_merges_multiple_houses(mock_post, caplog):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.user_id = "user-id"

    mock_post.return_value = {
        "status": "OK",
        "houses": {
            "1": [{"id": "10", "tipo": "ECO"}],
            "2": [{"id": "20", "tipo": "ECO"}],
        },
        "ecoIDs": ["10", "20"],
        "eco3IDs": [],
    }

    await api.set_house_and_device_ids()

    assert api.house_ids == ["1", "2"]
    assert api.ecocomfort2_ids == ["10", "20"]
    assert api.ecocomfort3_ids == []
    assert "Error while getting houses" not in caplog.text


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_house_and_device_ids_logs_devices_of_other_families(mock_post, caplog):
    caplog.set_level(logging.INFO)
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.user_id = "user-id"

    mock_post.return_value = {
        "status": "OK",
        "houses": {
            "1": [
                {"id": "10", "tipo": "ECO"},
                {"id": "11", "tipo": "CH"},
                {"id": "50", "tipo": "RHINO"},
            ]
        },
        "ecoIDs": ["10"],
        "eco3IDs": [],
    }

    await api.set_house_and_device_ids()

    assert api.ecocomfort2_ids == ["10"]
    assert "Ignoring unsupported IntelliClima devices: 11, 50" in caplog.text


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_house_and_device_ids_handles_missing_id_arrays(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.user_id = "user-id"

    mock_post.return_value = {"status": "OK", "houses": {}}

    await api.set_house_and_device_ids()

    assert api.ecocomfort2_ids == []
    assert api.ecocomfort3_ids == []


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_house_and_device_ids_propagates_errors(mock_post):
    # A swallowed failure would leave the ID lists empty, which reads exactly like an
    # account with no supported devices.
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.user_id = "user-id"

    mock_post.side_effect = IntelliClimaAPIError("boom")

    with pytest.raises(IntelliClimaAPIError):
        await api.set_house_and_device_ids()
