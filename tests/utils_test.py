import argparse
import pytest
import utils

from _pytest.monkeypatch import MonkeyPatch


from typing import Iterator


_ENV_VARS = [
    'CHROMEDRIVER_PATH',
    'CHROMEDRIVER_PATH',
    'USE_CHROMEDRIVER_ON_PATH',
    'MFA_TOKEN',
]


@pytest.fixture()
def test_env(monkeypatch: MonkeyPatch) -> Iterator[MonkeyPatch]:
  for envName in _ENV_VARS:
    monkeypatch.delenv(envName, raising=False)
  yield monkeypatch


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
  expected.show_browser = True
  expected.scrape_accounts = True
  expected.scrape_transactions = False
  assert utils.ScraperOptions.fromArgsAndEnv(args) == expected

  args = parser.parse_args(["--types=transactions", "--debug"])
  expected = utils.ScraperOptions()
  expected.show_browser = True
  expected.scrape_accounts = False
  expected.scrape_transactions = True
  assert utils.ScraperOptions.fromArgsAndEnv(args) == expected

  del test_env


def test_scraper_option_env(test_env: MonkeyPatch) -> None:
  parser: argparse.ArgumentParser = utils.ConstructArgumentParser()
  args = parser.parse_args([])
  with test_env.context() as env:
    env.setenv('CHROMEDRIVER_PATH', '/test/path/to/driver')
    assert utils.ScraperOptions.fromArgsAndEnv(
        args).chromedriver_download_path == "/test/path/to/driver"

  with test_env.context() as env:
    env.setenv('USE_CHROMEDRIVER_ON_PATH', 'true')
    assert utils.ScraperOptions.fromArgsAndEnv(args).use_chromedriver_on_path
    env.setenv('USE_CHROMEDRIVER_ON_PATH', 'yes')
    assert utils.ScraperOptions.fromArgsAndEnv(args).use_chromedriver_on_path
    env.setenv('USE_CHROMEDRIVER_ON_PATH', 'y')
    assert utils.ScraperOptions.fromArgsAndEnv(args).use_chromedriver_on_path
    env.setenv('USE_CHROMEDRIVER_ON_PATH', 't')
    assert utils.ScraperOptions.fromArgsAndEnv(args).use_chromedriver_on_path
    env.setenv('USE_CHROMEDRIVER_ON_PATH', '1')
    assert utils.ScraperOptions.fromArgsAndEnv(args).use_chromedriver_on_path

  with test_env.context() as env:
    env.setenv('CHROME_SESSION_PATH', '/path/to/session')
    assert utils.ScraperOptions.fromArgsAndEnv(
        args).session_path == '/path/to/session'

  with test_env.context() as env:
    env.setenv('MFA_TOKEN', '12345')
    options = utils.ScraperOptions.fromArgsAndEnv(args)
    assert options.mfa_method == 'soft-token'
    assert options.mfa_token == '12345'
