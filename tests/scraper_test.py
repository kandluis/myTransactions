import scraper

from _pytest.monkeypatch import MonkeyPatch

from google.oauth2 import service_account
from unittest.mock import MagicMock


def test_scraper(
    test_env: MonkeyPatch,
    test_creds: service_account.Credentials,
    mockApi: MagicMock,
    mockSheet: MagicMock,
    mocker,
) -> None:
    test_env.setenv("MFA_TOKEN", "GEZDGNBV")
    mocker.patch.object(scraper.remote, "Authenticate", return_value=mockApi)
    sheetsClient = mocker.MagicMock()
    sheetsClient.open.return_value = mockSheet
    mocker.patch.object(scraper.pygsheets, "authorize", return_value=sheetsClient)
    scraper.main([])

    del test_creds
