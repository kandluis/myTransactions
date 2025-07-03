import runpy
import scraper
import sys

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

def test_scraper_debug(
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
    scraper.main(["--debug"])

    del test_creds

def test_main_entrypoint(mocker):
    mocker.patch.object(scraper, "main")
    # Clear argv to avoid pytest args being passed to scraper
    sys.argv = ["scraper.py"]
    runpy.run_module("scraper", run_name="__main__")
