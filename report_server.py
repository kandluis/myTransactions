"""Flask service for generating and serving token-protected spend reports."""

from __future__ import annotations

import hmac
import os
from pathlib import Path
import threading
from typing import Optional

from flask import Flask, Response, jsonify, request, send_from_directory

import report_publisher

app = Flask(__name__)
_generate_lock = threading.Lock()


def _report_token() -> str:
    return os.getenv("REPORT_TOKEN", "")


def _configured_base_url() -> str:
    return os.getenv("REPORT_BASE_URL", "")


def _report_dir() -> Path:
    return Path(
        os.getenv("REPORT_OUTPUT_DIR", str(report_publisher.DEFAULT_REPORT_DIR))
    )


def _request_token() -> Optional[str]:
    header_token = request.headers.get("X-Report-Token")
    return request.args.get("token") or header_token


def is_authorized_token(token: Optional[str]) -> bool:
    """Return whether token matches REPORT_TOKEN."""
    expected = _report_token()
    if not expected or token is None:
        return False
    return hmac.compare_digest(token, expected)


def _forbidden() -> tuple[Response, int]:
    return jsonify({"error": "forbidden"}), 403


@app.get("/health")
def health() -> Response:
    return jsonify({"status": "ok"})


@app.get("/reports/<path:filename>")
def serve_report(filename: str) -> Response | tuple[Response, int]:
    if not is_authorized_token(_request_token()):
        return _forbidden()
    if filename not in {
        report_publisher.SPEND_REPORT_FILENAME,
        report_publisher.OUTLIER_REPORT_FILENAME,
    }:
        return jsonify({"error": "not found"}), 404
    return send_from_directory(_report_dir(), filename)


@app.post("/generate")
def generate() -> tuple[Response, int]:
    if not is_authorized_token(_request_token()):
        return _forbidden()

    if not _generate_lock.acquire(blocking=False):
        return jsonify({"error": "generation already running"}), 409

    try:
        token = _report_token()
        result = report_publisher.publish_spend_report(
            source="sheets",
            output_dir=_report_dir(),
            base_url=_configured_base_url(),
            token=token,
            update_sheet=True,
        )
        status_code = 200 if result.status == "success" else 500
        return jsonify(result.as_dict()), status_code
    finally:
        _generate_lock.release()
