import empower
import pytest
import re

from unittest.mock import MagicMock

def test_api_request_non_ok_status(mocker):
    session = mocker.MagicMock()
    response = mocker.MagicMock()
    response.status_code = 404
    response.headers = {}  # Fix: ensure headers is a dict
    session.request.return_value = response
    pc = empower.PersonalCapital()
    pc.session = session

    with pytest.raises(RuntimeError):
        pc._api_request("get", "/test")


def test_api_request_non_json_response(mocker):
    session = mocker.MagicMock()
    response = mocker.MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/html"}
    session.request.return_value = response
    pc = empower.PersonalCapital()
    pc.session = session

    with pytest.raises(RuntimeError):
        pc._api_request("get", "/test")


def test_api_request_success_false(mocker):
    session = mocker.MagicMock()
    response = mocker.MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.text = '{"spHeader": {"success": false}}'
    session.request.return_value = response
    pc = empower.PersonalCapital()
    pc.session = session

    with pytest.raises(RuntimeError):
        pc._api_request("get", "/test")


def test_api_request_expired_session(mocker):
    session = mocker.MagicMock()
    response = mocker.MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.text = '{"spHeader": {"success": false, "errors": [{"code": 201}]}}'
    session.request.return_value = response
    pc = empower.PersonalCapital()
    pc.session = session

    with pytest.raises(empower.PersonalCapitalSessionExpiredException):
        pc._api_request("get", "/test")


def test_login_invalid_mfa_method():
    pc = empower.PersonalCapital()
    with pytest.raises(ValueError, match="Auth method invalid is not supported"):
        pc.login("test", "test", mfa_method="invalid")


def test_handle_mfa_totp_no_token(mocker):
    pc = empower.PersonalCapital()
    mocker.patch.object(pc, '_api_request')
    with pytest.raises(ValueError, match="Specified mfa_method: totp without token."):
        pc._handle_mfa(mfa_method="totp", mfa_token=None)


def test_handle_mfa_interactive(mocker):
    pc = empower.PersonalCapital()
    mocker.patch.object(pc, '_api_request')
    mocker.patch('empower.getpass.getpass', return_value='123456')
    pc._handle_mfa(mfa_method="sms", mfa_token=None)
    empower.getpass.getpass.assert_called_once_with('Enter 2 factor code: ')
    pc._api_request.assert_any_call(
        'post',
        '/api/credential/authenticateSms',
        {
            'challengeReason': 'DEVICE_AUTH',
            'challengeMethod': 'OP',
            'bindDevice': 'false',
            'code': '123456'
        }
    )


def test_login_no_csrf(mocker):
    session = mocker.MagicMock()
    response = mocker.MagicMock()
    response.text = ""
    session.get.return_value = response
    pc = empower.PersonalCapital()
    pc.session = session

    with pytest.raises(RuntimeError, match="Failed to extract csrf from session"):
        pc.login("test", "test", mfa_method="sms")


def test_is_logged_in_false():
    pc = empower.PersonalCapital()
    assert not pc.is_logged_in()


def test_is_logged_in_true(mocker):
    pc = empower.PersonalCapital()
    pc._email = "test@test.com"
    mocker.patch.object(pc, 'get_account_data')
    assert pc.is_logged_in()
    pc.get_account_data.assert_called_once()


def test_is_logged_in_session_expired(mocker):
    pc = empower.PersonalCapital()
    pc._email = "test@test.com"
    mocker.patch.object(pc, 'get_account_data', side_effect=empower.PersonalCapitalSessionExpiredException)
    assert not pc.is_logged_in()
    pc.get_account_data.assert_called_once()