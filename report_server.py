"""Flask service for generating and serving token-protected spend reports."""

from __future__ import annotations

import hmac
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Optional
from uuid import uuid4

from flask import Flask, Response, jsonify, request, send_from_directory

import report_publisher

app = Flask(__name__)
_job_state_lock = Lock()


def _configure_logging() -> None:
    """Make module INFO logs visible under Gunicorn and local runs."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        root_logger.addHandler(handler)

    logging.getLogger("gunicorn.error").setLevel(logging.INFO)
    logging.getLogger("gunicorn.access").setLevel(logging.INFO)


_configure_logging()


@dataclass
class GenerateJob:
    job_id: str
    state: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    report_url: str = ""
    outlier_url: str = ""
    error: str = ""
    source: str = "sheets"

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["active"] = self.state in {"queued", "running"}
        return payload


_current_job: Optional[GenerateJob] = None
_last_terminal_job: Optional[GenerateJob] = None


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_job_id() -> str:
    return uuid4().hex


def _set_current_job(job: GenerateJob) -> None:
    global _current_job
    _current_job = job


def _mark_terminal(job: GenerateJob) -> None:
    global _current_job, _last_terminal_job
    with _job_state_lock:
        job.finished_at = _utc_now()
        _current_job = None
        _last_terminal_job = job


def _get_current_job(job_id: str) -> Optional[GenerateJob]:
    with _job_state_lock:
        if _current_job is not None and _current_job.job_id == job_id:
            return _current_job
        return None


def _get_job_snapshot() -> Optional[GenerateJob]:
    with _job_state_lock:
        return _current_job or _last_terminal_job


def _run_generate_job(job_id: str) -> None:
    job = _get_current_job(job_id)
    if job is None:
        return

    try:
        with _job_state_lock:
            job.state = "running"
            job.started_at = _utc_now()
        result = report_publisher.publish_spend_report(
            source="sheets",
            output_dir=_report_dir(),
            base_url=_configured_base_url(),
            token=_report_token(),
            update_sheet=True,
            include_heatmap=False,
            include_total_spend=False,
            include_category_share=False,
            include_customdata=False,
            job_id=job.job_id,
        )
        with _job_state_lock:
            if _current_job is not None and _current_job.job_id == job_id:
                _current_job.report_url = result.report_url
                _current_job.outlier_url = result.outlier_url
                _current_job.error = result.error
                _current_job.state = (
                    "succeeded" if result.status == "success" else "failed"
                )
    except Exception as exc:  # pragma: no cover - defensive guard
        with _job_state_lock:
            if _current_job is not None and _current_job.job_id == job_id:
                _current_job.state = "failed"
                _current_job.error = str(exc)
    finally:
        _mark_terminal(job)


def _status_payload() -> dict[str, object]:
    job = _get_job_snapshot()
    if job is None:
        return {"state": "idle", "active": False}
    return job.to_dict()


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

    with _job_state_lock:
        if _current_job is not None and _current_job.state in {
            "queued",
            "running",
        }:
            payload = _current_job.to_dict()
            payload["error"] = "generation already running"
            return jsonify(payload), 409

        job = GenerateJob(
            job_id=_new_job_id(),
            state="queued",
            created_at=_utc_now(),
            source="sheets",
        )
        _set_current_job(job)
        worker = Thread(target=_run_generate_job, args=(job.job_id,), daemon=True)
        worker.start()
        payload = job.to_dict()
        payload["status_url"] = f"/generate/status?token={_report_token()}"
        return jsonify(payload), 202


@app.get("/generate/status")
def generate_status() -> Response | tuple[Response, int]:
    if not is_authorized_token(_request_token()):
        return _forbidden()
    return jsonify(_status_payload())
