from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import IntelliClimaAPI
from pyintelliclima.intelliclima_types import IntelliClimaFilterStatus

pytestmark = pytest.mark.asyncio


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_get_filter_status_dirty(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")

    mock_post.return_value = {
        "status": "OK",
        "action": "CALCULATE",
        "serial": "12345678",
        "is_active": True,
        "from_date": "2025-10-28 00:00:00",
        "stats": [
            {
                "night_tot_hour": "15237",
                "low_tot_hour": "4355",
                "medium_tot_hour": "81",
                "high_tot_hour": "127",
                "boost_tot_hour": "3",
            }
        ],
        "totale": 5923.7,
        "change_filter": True,
    }

    status = await api.ecocomfort.get_filter_status("12345678")

    assert isinstance(status, IntelliClimaFilterStatus)
    assert status.change_filter is True
    assert status.totale == 5923.7
    assert status.stats[0].night_tot_hour == "15237"

    mock_post.assert_awaited_once()
    called_args, called_kwargs = mock_post.call_args
    assert called_args[1] == "eco/filters/"
    assert called_kwargs["json_payload"] == {"serial": "12345678", "action": "CALCULATE"}


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_get_filter_status_clean(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")

    mock_post.return_value = {
        "status": "OK",
        "action": "CALCULATE",
        "serial": "12345678",
        "is_active": True,
        "from_date": "2026-07-28 00:00:00",
        "stats": [],
        "totale": 0,
        "change_filter": False,
    }

    status = await api.ecocomfort.get_filter_status("12345678")

    assert status.change_filter is False
    assert status.stats == []


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_filter_tracking_active(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")

    mock_post.return_value = {
        "status": "OK",
        "action": "ACTIVATE",
        "serial": "12345678",
        "is_active": True,
        "from_date": "2026-08-04 00:00:00",
        "stats": [],
        "totale": 0,
        "change_filter": False,
    }

    status = await api.ecocomfort.set_filter_tracking_active("12345678", True)

    assert status.is_active is True
    called_args, called_kwargs = mock_post.call_args
    assert called_args[1] == "eco/filters/"
    assert called_kwargs["json_payload"] == {"serial": "12345678", "action": "ACTIVATE"}


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_filter_tracking_inactive(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")

    mock_post.return_value = {
        "status": "OK",
        "action": "DEACTIVATE",
        "serial": "12345678",
        "is_active": False,
        "from_date": "2026-07-28 00:00:00",
        "stats": [],
        "totale": 0,
        "change_filter": False,
    }

    status = await api.ecocomfort.set_filter_tracking_active("12345678", False)

    assert status.is_active is False
    called_kwargs = mock_post.call_args.kwargs
    assert called_kwargs["json_payload"] == {"serial": "12345678", "action": "DEACTIVATE"}


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_reset_filter_counter(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")

    mock_post.return_value = {
        "status": "OK",
        "action": "RESET",
        "serial": "12345678",
        "is_active": True,
        "from_date": "2026-08-04 00:00:00",
        "stats": [],
        "totale": 0,
        "change_filter": False,
    }

    status = await api.ecocomfort.reset_filter_counter("12345678")

    assert status.from_date == "2026-08-04 00:00:00"
    assert status.totale == 0
    called_kwargs = mock_post.call_args.kwargs
    assert called_kwargs["json_payload"] == {"serial": "12345678", "action": "RESET"}


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_eco3_filter_status_uses_eco3_endpoint(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")

    mock_post.return_value = {
        "status": "OK",
        "action": "CALCULATE",
        "serial": "12345678",
        "is_active": True,
        "from_date": "2026-08-04 00:00:00",
        "stats": [],
        "totale": 0,
        "change_filter": False,
    }

    await api.ecocomfort3.get_filter_status("12345678")

    assert mock_post.call_args.args[1] == "eco3/filters/"


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_eco3_reset_filter_counter_also_clears_the_device(mock_post):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")

    mock_post.return_value = {
        "status": "OK",
        "action": "RESET",
        "serial": "12345678",
        "is_active": True,
        "from_date": "2026-08-04 00:00:00",
        "stats": [],
        "totale": 0,
        "change_filter": False,
    }

    status = await api.ecocomfort3.reset_filter_counter("12345678")

    assert status.from_date == "2026-08-04 00:00:00"
    assert mock_post.await_args_list[0].args[1] == "eco3/filters/"
    assert mock_post.await_args_list[0].kwargs["json_payload"] == {
        "serial": "12345678",
        "action": "RESET",
    }
    # The endpoint only clears the server-side counter; the frame clears the unit.
    assert mock_post.await_args_list[1].args[1] == "eco3/send/"
    assert mock_post.await_args_list[1].kwargs["json_payload"] == {
        "trama": "0A12345678001026001A001A00000000320D"
    }
