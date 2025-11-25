from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError

from pyintelliclima.api import IntelliClimaAPI, IntelliClimaAuthError

pytestmark = pytest.mark.asyncio


def _make_api():
    session = MagicMock()
    return IntelliClimaAPI(session, username="user", password="pass")


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
@patch.object(IntelliClimaAPI, "set_house_and_device_ids", new_callable=AsyncMock)
async def test_authenticate_success(mock_set_house_devices, mock_post):
    api = _make_api()
    mock_post.return_value = {
        "status": "OK",
        "token": "token123",
        "id": "user-id",
        "error": "",
    }

    result = await api.authenticate()

    assert result is True
    assert api.auth_token == "token123"
    assert api.user_id == "user-id"
    assert api._token_headers["TOKEN"] == "token123"
    assert api._token_headers["TOKENID"] == "user-id"
    mock_set_house_devices.assert_awaited_once()


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_authenticate_no_password_error(mock_post):
    api = _make_api()
    mock_post.return_value = {
        "status": "OK",
        "token": None,
        "id": None,
        "error": "NO_PASSWORD",
    }

    with pytest.raises(IntelliClimaAuthError):
        await api.authenticate()


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_authenticate_missing_token(mock_post):
    api = _make_api()
    mock_post.return_value = {
        "status": "OK",
        "token": None,
        "id": "user-id",
        "error": "",
    }

    with pytest.raises(IntelliClimaAuthError):
        await api.authenticate()


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_authenticate_missing_user_id(mock_post):
    api = _make_api()
    mock_post.return_value = {
        "status": "OK",
        "token": "token123",
        "id": None,
        "error": "",
    }

    with pytest.raises(IntelliClimaAuthError):
        await api.authenticate()


@patch("pyintelliclima.api.post_to_session", new_callable=AsyncMock)
async def test_authenticate_client_error_wrapped(mock_post):
    api = _make_api()
    mock_post.side_effect = ClientError("boom")

    with pytest.raises(IntelliClimaAuthError):
        await api.authenticate()
