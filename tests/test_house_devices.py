from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyintelliclima.api import IntelliClimaAPI

pytestmark = pytest.mark.asyncio


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_house_and_device_ids_filters_ch(mock_post, caplog):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.user_id = "user-id"

    mock_post.return_value = {
        "status": "OK",
        "houses": {
            "1": [
                {"id": "10", "tipo": "ECO"},
                {"id": "11", "tipo": "CH"},
            ]
        },
    }

    await api.set_house_and_device_ids()

    assert api.house_id == "1"
    assert api.device_id_types == {"10": "ECO"}
    assert "Error while getting houses" not in caplog.text


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_set_house_and_device_ids_logs_error(mock_post, caplog):
    api = IntelliClimaAPI(MagicMock(), username="user", password="pass")
    api.user_id = "user-id"

    mock_post.side_effect = RuntimeError("boom")

    await api.set_house_and_device_ids()

    assert "Error while getting houses for user: user-id" in caplog.text
