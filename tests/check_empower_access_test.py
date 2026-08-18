from pathlib import Path

import empower
from scripts import check_empower_access


def test_check_saved_session_reports_available(mocker, capsys, tmp_path: Path) -> None:
    connection = mocker.patch.object(
        check_empower_access.empower, "PersonalCapital"
    ).return_value
    connection.load_session.return_value = True
    connection.get_account_data.return_value = {"sensitive": "not printed"}

    result = check_empower_access.check_saved_session(tmp_path / "session.pkl")

    assert result == check_empower_access.EXIT_AVAILABLE
    assert capsys.readouterr().out == (
        "AVAILABLE: The saved Empower session passed one account API check.\n"
    )


def test_check_saved_session_reports_cloudflare_challenge(
    mocker, capsys, tmp_path: Path
) -> None:
    connection = mocker.patch.object(
        check_empower_access.empower, "PersonalCapital"
    ).return_value
    connection.load_session.return_value = True
    connection.get_account_data.side_effect = (
        empower.PersonalCapitalCloudflareChallengeException("retry later")
    )

    result = check_empower_access.check_saved_session(tmp_path / "session.pkl")

    assert result == check_empower_access.EXIT_CHALLENGED
    assert capsys.readouterr().out == "CHALLENGED: retry later\n"


def test_check_saved_session_reports_expired(mocker, capsys, tmp_path: Path) -> None:
    connection = mocker.patch.object(
        check_empower_access.empower, "PersonalCapital"
    ).return_value
    connection.load_session.return_value = True
    connection.get_account_data.side_effect = (
        empower.PersonalCapitalSessionExpiredException()
    )

    result = check_empower_access.check_saved_session(tmp_path / "session.pkl")

    assert result == check_empower_access.EXIT_SESSION_EXPIRED
    assert "must be refreshed with MFA" in capsys.readouterr().out


def test_check_saved_session_reports_missing_file(
    mocker, capsys, tmp_path: Path
) -> None:
    connection = mocker.patch.object(
        check_empower_access.empower, "PersonalCapital"
    ).return_value
    connection.load_session.return_value = False

    result = check_empower_access.check_saved_session(tmp_path / "missing.pkl")

    assert result == check_empower_access.EXIT_ERROR
    assert "Could not load saved session" in capsys.readouterr().out
