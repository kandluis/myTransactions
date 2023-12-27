import argparse
import pytest
import utils

from _pytest.monkeypatch import MonkeyPatch


def test_scraper_options_failure() -> None:
    parser: argparse.ArgumentParser = utils.ConstructArgumentParser()
    args: argparse.Namespace = parser.parse_args(["--types=invalid"])

    with pytest.raises(utils.ScraperError):
        utils.ScraperOptions.fromArgsAndEnv(args)


def test_scraper_options_defaults(test_env: MonkeyPatch) -> None:
    parser: argparse.ArgumentParser = utils.ConstructArgumentParser()
    args = parser.parse_args([])
    assert utils.ScraperOptions.fromArgsAndEnv(args) == utils.ScraperOptions()

    del test_env


def test_scraper_option_args(test_env: MonkeyPatch) -> None:
    parser: argparse.ArgumentParser = utils.ConstructArgumentParser()
    args = parser.parse_args(["--types=accounts", "--debug"])
    expected = utils.ScraperOptions()
    expected.scrape_accounts = True
    expected.scrape_transactions = False
    assert utils.ScraperOptions.fromArgsAndEnv(args) == expected

    args = parser.parse_args(["--types=transactions", "--debug"])
    expected = utils.ScraperOptions()
    expected.scrape_accounts = False
    expected.scrape_transactions = True
    assert utils.ScraperOptions.fromArgsAndEnv(args) == expected

    del test_env


def test_scraper_option_env(test_env: MonkeyPatch) -> None:
    parser: argparse.ArgumentParser = utils.ConstructArgumentParser()
    args = parser.parse_args([])

    with test_env.context() as env:
        env.setenv("MFA_TOKEN", "12345")
        options = utils.ScraperOptions.fromArgsAndEnv(args)
        assert options.mfa_method == "totp"
        assert options.mfa_token == "12345"
