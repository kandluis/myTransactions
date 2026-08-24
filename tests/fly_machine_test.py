from unittest.mock import MagicMock

import pytest

import fly_machine


def test_start_scraper_machine_requires_runtime_configuration(monkeypatch) -> None:
    monkeypatch.delenv("FLY_API_TOKEN", raising=False)
    monkeypatch.delenv("SCRAPER_MACHINE_ID", raising=False)

    assert not fly_machine.is_configured()
    with pytest.raises(fly_machine.FlyMachineError, match="not configured"):
        fly_machine.start_scraper_machine()


def test_start_scraper_machine_posts_to_the_configured_machine(monkeypatch) -> None:
    response = MagicMock(status_code=200)
    post = MagicMock(return_value=response)
    monkeypatch.setenv("FLY_API_TOKEN", "runtime-token")
    monkeypatch.setenv("SCRAPER_MACHINE_ID", "scraper-machine")
    monkeypatch.setenv("FLY_APP_NAME", "test-app")
    monkeypatch.setattr(fly_machine.requests, "post", post)

    fly_machine.start_scraper_machine()

    assert post.call_args.args[0].endswith(
        "/v1/apps/test-app/machines/scraper-machine/start"
    )
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer runtime-token"


def test_start_scraper_machine_accepts_an_already_starting_worker(monkeypatch) -> None:
    monkeypatch.setenv("FLY_API_TOKEN", "runtime-token")
    monkeypatch.setenv("SCRAPER_MACHINE_ID", "scraper-machine")
    monkeypatch.setattr(
        fly_machine.requests, "post", MagicMock(return_value=MagicMock(status_code=409))
    )

    fly_machine.start_scraper_machine()
