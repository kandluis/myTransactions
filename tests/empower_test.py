import empower
import pytest


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


def test_login(mocker):
    pc = empower.PersonalCapital()
    mock_session = mocker.MagicMock()
    pc.session = mock_session

    # Mock Step 1: Initial Authentication
    mock_auth_response = mocker.MagicMock()
    mock_auth_response.json.return_value = {"success": True, "idToken": "test_token"}
    mock_session.post.return_value = mock_auth_response

    # Mock Step 2: Token Authentication
    mock_token_response = {
        "spHeader": {
            "success": False,
            "errors": [{"code": 200, "message": "Authorization required."}],
            "csrf": "test_csrf",
        }
    }
    mocker.patch.object(pc, "_api_request", return_value=mock_token_response)

    # Mock Step 4: Authenticate SMS
    mocker.patch("empower.input", return_value="123456")

    pc.login("test_email", "test_password")

    # Assertions
    mock_session.post.assert_called_once()
    pc._api_request.assert_any_call(
        "post",
        "/api/credential/authenticateToken",
        data={"idToken": "test_token"},
        check_success=False,
    )
    pc._api_request.assert_any_call(
        "post", "/api/credential/challengeSmsFreemium", mocker.ANY
    )
    pc._api_request.assert_any_call(
        "post", "/api/credential/authenticateSmsFreemium", mocker.ANY
    )
    assert pc._email == "test_email"
    assert pc._csrf == "test_csrf"


def test_is_logged_in_false():
    pc = empower.PersonalCapital()
    assert not pc.is_logged_in()


def test_is_logged_in_true(mocker):
    pc = empower.PersonalCapital()
    pc._email = "test@test.com"
    mocker.patch.object(pc, "get_account_data")
    assert pc.is_logged_in()
    pc.get_account_data.assert_called_once()


def test_is_logged_in_session_expired(mocker):
    pc = empower.PersonalCapital()
    pc._email = "test@test.com"
    mocker.patch.object(
        pc,
        "get_account_data",
        side_effect=empower.PersonalCapitalSessionExpiredException,
    )
    assert not pc.is_logged_in()
    pc.get_account_data.assert_called_once()
