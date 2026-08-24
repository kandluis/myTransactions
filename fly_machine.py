"""Minimal Fly Machines API client for starting the one-shot scraper worker."""

from __future__ import annotations

import os

import requests


class FlyMachineError(RuntimeError):
    """An actionable failure while dispatching work to the scraper Machine."""


def is_configured() -> bool:
    """Return whether this service can dispatch a run to the scraper Machine."""
    return bool(os.getenv("FLY_API_TOKEN") and os.getenv("SCRAPER_MACHINE_ID"))


def start_scraper_machine() -> None:
    """Start the stopped one-shot scraper Machine through Fly's Machines API."""
    token = os.getenv("FLY_API_TOKEN", "")
    machine_id = os.getenv("SCRAPER_MACHINE_ID", "")
    app_name = os.getenv("FLY_APP_NAME", "mint-scraper")
    api_host = os.getenv("FLY_API_HOSTNAME", "https://api.machines.dev").rstrip("/")
    if not token or not machine_id:
        raise FlyMachineError("The on-demand scraper worker is not configured")

    try:
        response = requests.post(
            f"{api_host}/v1/apps/{app_name}/machines/{machine_id}/start",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise FlyMachineError("Could not start the on-demand scraper worker") from exc

    # A concurrent scheduled/manual start means the one-shot worker is already
    # booting or running and will consume the queued Sheet-backed job.
    if response.status_code in {200, 201, 202, 409}:
        return
    raise FlyMachineError("Fly could not start the on-demand scraper worker")


def scraper_machine_state() -> str:
    """Return the current state of the configured one-shot scraper Machine."""
    token = os.getenv("FLY_API_TOKEN", "")
    machine_id = os.getenv("SCRAPER_MACHINE_ID", "")
    app_name = os.getenv("FLY_APP_NAME", "mint-scraper")
    api_host = os.getenv("FLY_API_HOSTNAME", "https://api.machines.dev").rstrip("/")
    if not token or not machine_id:
        raise FlyMachineError("The on-demand scraper worker is not configured")

    try:
        response = requests.get(
            f"{api_host}/v1/apps/{app_name}/machines/{machine_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise FlyMachineError("Could not check the on-demand scraper worker") from exc
    if not response.ok:
        raise FlyMachineError("Could not check the on-demand scraper worker")
    return str(payload.get("state", "unknown"))
