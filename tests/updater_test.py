import os
import runpy
import sys
import updater

from _pytest.monkeypatch import MonkeyPatch
from google.oauth2 import service_account
from unittest.mock import MagicMock


def test_updater_dry_run(
    test_env: MonkeyPatch,
    test_creds: service_account.Credentials,
    mockSheet: MagicMock,
    mocker,
) -> None:
    sheetsClient = mocker.MagicMock()
    sheetsClient.open.return_value = mockSheet
    mocker.patch.object(updater.pygsheets, "authorize", return_value=sheetsClient)

    # Run main with dry_run
    updater.main(["--dry_run"])

    # Verify the local file is created
    assert os.path.exists("transactions_updated.csv")

    # Cleanup local file
    try:
        os.remove("transactions_updated.csv")
    except OSError:
        pass


def test_updater_write(
    test_env: MonkeyPatch,
    test_creds: service_account.Credentials,
    mockSheet: MagicMock,
    mocker,
) -> None:
    sheetsClient = mocker.MagicMock()
    sheetsClient.open.return_value = mockSheet
    mocker.patch.object(updater.pygsheets, "authorize", return_value=sheetsClient)

    # Spy on remote.UpdateGoogleSheet
    spy_update = mocker.spy(updater.remote, "UpdateGoogleSheet")

    # Run main in write mode (no args)
    updater.main([])

    # Verify UpdateGoogleSheet was called
    spy_update.assert_called_once()

    # Cleanup any local files if created
    if os.path.exists("transactions_updated.csv"):
        os.remove("transactions_updated.csv")


def test_main_entrypoint(
    test_env: MonkeyPatch,
    test_creds: service_account.Credentials,
    mockSheet: MagicMock,
    mocker,
) -> None:
    sheetsClient = mocker.MagicMock()
    sheetsClient.open.return_value = mockSheet
    mocker.patch.object(updater.pygsheets, "authorize", return_value=sheetsClient)

    # Mock sys.argv to emulate command-line invocation
    sys.argv = ["updater.py", "--dry_run"]
    runpy.run_module("updater", run_name="__main__")

    # Verify the local file is created
    assert os.path.exists("transactions_updated.csv")

    # Cleanup local file
    try:
        os.remove("transactions_updated.csv")
    except OSError:
        pass
