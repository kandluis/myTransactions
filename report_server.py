"""Flask service for generating and serving token-protected spend reports."""

from __future__ import annotations

import hmac
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Optional
from uuid import uuid4

from flask import (
    Flask,
    Response,
    jsonify,
    request,
    render_template_string,
    session,
    send_from_directory,
)

import auth
import config
import empower
import report_publisher
import remote
import scraper
import plaid_source
import utils

app = Flask(__name__)
app.secret_key = os.getenv(
    "FLASK_SESSION_SECRET", os.getenv("REPORT_TOKEN", "development-only-change-me")
)
_job_state_lock = Lock()
_plaid_approval_lock = Lock()
_SCRAPE_FRESHNESS_WINDOW = timedelta(
    seconds=int(os.getenv("SCRAPE_FRESHNESS_SECONDS", "900"))
)


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


@dataclass
class ScrapeJob:
    job_id: str
    state: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    last_successful_at: str = ""
    skip_reason: str = ""
    error: str = ""
    error_code: str = ""
    source: str = "plaid"
    freshness_window_seconds: int = int(_SCRAPE_FRESHNESS_WINDOW.total_seconds())

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["active"] = self.state in {"queued", "running"}
        return payload


_current_job: Optional[GenerateJob] = None
_last_terminal_job: Optional[GenerateJob] = None
_current_scrape_job: Optional[ScrapeJob] = None
_last_terminal_scrape_job: Optional[ScrapeJob] = None


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


def _set_current_scrape_job(job: ScrapeJob) -> None:
    global _current_scrape_job
    _current_scrape_job = job


def _mark_terminal(job: GenerateJob) -> None:
    global _current_job, _last_terminal_job
    with _job_state_lock:
        job.finished_at = _utc_now()
        _current_job = None
        _last_terminal_job = job


def _mark_scrape_terminal(job: ScrapeJob) -> None:
    global _current_scrape_job, _last_terminal_scrape_job
    with _job_state_lock:
        job.finished_at = _utc_now()
        _current_scrape_job = None
        _last_terminal_scrape_job = job


def _get_current_job(job_id: str) -> Optional[GenerateJob]:
    with _job_state_lock:
        if _current_job is not None and _current_job.job_id == job_id:
            return _current_job
        return None


def _get_current_scrape_job(job_id: str) -> Optional[ScrapeJob]:
    with _job_state_lock:
        if _current_scrape_job is not None and _current_scrape_job.job_id == job_id:
            return _current_scrape_job
        return None


def _get_job_snapshot() -> Optional[GenerateJob]:
    with _job_state_lock:
        return _current_job or _last_terminal_job


def _get_scrape_job_snapshot() -> Optional[ScrapeJob]:
    with _job_state_lock:
        return _current_scrape_job or _last_terminal_scrape_job


def _load_last_scrape_at() -> Optional[datetime]:
    try:
        sheet = report_publisher.open_configured_spreadsheet()
        settings_ws = sheet.worksheet_by_title(title=config.GLOBAL.SETTINGS_SHEET_TITLE)
        return remote.read_last_scrape_at(settings_ws)
    except Exception as exc:  # pragma: no cover - best effort freshness hint
        logging.getLogger(__name__).info(
            "Could not read last scrape timestamp: %s", exc
        )
        return None


def _scrape_is_fresh(last_scrape_at: Optional[datetime]) -> bool:
    if last_scrape_at is None:
        return False
    return datetime.now(timezone.utc) - last_scrape_at <= _SCRAPE_FRESHNESS_WINDOW


def _scrape_age_seconds(last_scrape_at: Optional[datetime]) -> Optional[int]:
    if last_scrape_at is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - last_scrape_at).total_seconds()))


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


def _run_scrape_job(job_id: str) -> None:
    job = _get_current_scrape_job(job_id)
    if job is None:
        return

    try:
        with _job_state_lock:
            job.state = "running"
            job.started_at = _utc_now()
        options = utils.ScraperOptions()
        creds = None if plaid_source.is_configured() else auth.GetCredentials()
        scraper.scrape_and_push(options, creds)
        completed_at = _utc_now()
        with _job_state_lock:
            if _current_scrape_job is not None and _current_scrape_job.job_id == job_id:
                _current_scrape_job.state = "succeeded"
                _current_scrape_job.last_successful_at = completed_at
    except plaid_source.PlaidError as exc:
        with _job_state_lock:
            if _current_scrape_job is not None and _current_scrape_job.job_id == job_id:
                _current_scrape_job.state = "failed"
                _current_scrape_job.error_code = exc.code
                _current_scrape_job.error = str(exc)
    except empower.PersonalCapitalCloudflareChallengeException as exc:
        with _job_state_lock:
            if _current_scrape_job is not None and _current_scrape_job.job_id == job_id:
                _current_scrape_job.state = "failed"
                _current_scrape_job.error_code = "empower_cloudflare_challenge"
                _current_scrape_job.error = str(exc)
    except Exception as exc:  # pragma: no cover - defensive guard
        with _job_state_lock:
            if _current_scrape_job is not None and _current_scrape_job.job_id == job_id:
                _current_scrape_job.state = "failed"
                _current_scrape_job.error = str(exc)
    finally:
        _mark_scrape_terminal(job)


def _status_payload() -> dict[str, object]:
    job = _get_job_snapshot()
    if job is None:
        return {"state": "idle", "active": False}
    return job.to_dict()


def _scrape_status_payload() -> dict[str, object]:
    job = _get_scrape_job_snapshot()
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


@app.post("/scrape")
def scrape() -> tuple[Response, int]:
    if not is_authorized_token(_request_token()):
        return _forbidden()

    with _job_state_lock:
        if _current_scrape_job is not None and _current_scrape_job.state in {
            "queued",
            "running",
        }:
            payload = _current_scrape_job.to_dict()
            payload["error"] = "scrape already running"
            return jsonify(payload), 409

    if not scraper.scrape_lock_available():
        return jsonify({"error": "scrape already running"}), 409

    last_scrape_at = _load_last_scrape_at()
    if _scrape_is_fresh(last_scrape_at):
        job = ScrapeJob(
            job_id=_new_job_id(),
            state="skipped",
            created_at=_utc_now(),
            finished_at=_utc_now(),
            last_successful_at=last_scrape_at.isoformat() if last_scrape_at else "",
            skip_reason="last successful scrape is still within the freshness window",
            source="plaid" if plaid_source.is_configured() else "empower",
        )
        _mark_scrape_terminal(job)
        payload = job.to_dict()
        payload["age_seconds"] = _scrape_age_seconds(last_scrape_at)
        return jsonify(payload), 200

    with _job_state_lock:
        job = ScrapeJob(
            job_id=_new_job_id(),
            state="queued",
            created_at=_utc_now(),
            last_successful_at=last_scrape_at.isoformat() if last_scrape_at else "",
            source="plaid" if plaid_source.is_configured() else "empower",
        )
        _set_current_scrape_job(job)
        worker = Thread(target=_run_scrape_job, args=(job.job_id,), daemon=True)
        worker.start()
        payload = job.to_dict()
        payload["status_url"] = f"/scrape/status?token={_report_token()}"
        payload["age_seconds"] = _scrape_age_seconds(last_scrape_at)
        return jsonify(payload), 202


@app.get("/scrape/status")
def scrape_status() -> Response | tuple[Response, int]:
    if not is_authorized_token(_request_token()):
        return _forbidden()
    return jsonify(_scrape_status_payload())


def _open_plaid_sheet():
    return report_publisher.open_configured_spreadsheet()


def _require_plaid_configured() -> Optional[tuple[Response, int]]:
    if not plaid_source.is_configured():
        return (
            jsonify({"error": "Plaid is not configured", "error_code": "sync_failed"}),
            503,
        )
    return None


@app.get("/plaid/connect")
def plaid_connect() -> Response | tuple[Response, int]:
    """Create a one-time Link session outside the Apps Script iframe."""
    if not is_authorized_token(_request_token()):
        return _forbidden()
    unavailable = _require_plaid_configured()
    if unavailable:
        return unavailable
    reserve = request.args.get("use_reserve") == "1"
    store = plaid_source.SheetStateStore(_open_plaid_sheet())
    state = store.load()
    count = len(state.get("items", {}))
    if count >= plaid_source.MAX_ITEMS or (
        count >= plaid_source.MAX_ITEMS - plaid_source.RESERVED_ITEMS and not reserve
    ):
        return (
            jsonify(
                {
                    "error": "Plaid Item limit reached",
                    "error_code": "item_limit_reached",
                    "items": count,
                    "use_reserve_required": count
                    == plaid_source.MAX_ITEMS - plaid_source.RESERVED_ITEMS,
                }
            ),
            409,
        )
    try:
        link = plaid_source.PlaidClient().create_link_token()
    except plaid_source.PlaidError as exc:
        return jsonify({"error": str(exc), "error_code": exc.code}), 400
    session["plaid_link_authorized"] = True
    session["plaid_link_token"] = link["link_token"]
    return Response(
        render_template_string(
            """<!doctype html><title>Connect account</title>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<button id="connect">Connect Plaid account</button><p id="status"></p>
<script>
const status = document.getElementById('status');
async function exchange(public_token) {
  status.textContent = 'Saving connection and preparing review…';
  const response = await fetch('/plaid/exchange', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({public_token})
  });
  const result = await response.json();
  status.textContent = response.ok ? 'Connected. Review then approve below.' :
    (result.error || 'Could not connect.');
  if (response.ok) {
    const review = document.createElement('a');
    review.href = '/plaid/review' + window.location.search;
    review.textContent = 'Review staged import';
    document.body.appendChild(review);
  }
}
const handler = Plaid.create({token: {{ token|tojson }},
  receivedRedirectUri: {{ redirect_uri|tojson }}, onSuccess: exchange,
  onExit: err => { if (err) status.textContent = 'Link was not completed.'; }});
document.getElementById('connect').onclick = () => handler.open();
</script>""",
            token=link["link_token"],
            redirect_uri="",
        )
    )


@app.post("/plaid/exchange")
def plaid_exchange() -> Response | tuple[Response, int]:
    if not session.get("plaid_link_authorized"):
        return _forbidden()
    public_token = str((request.get_json(silent=True) or {}).get("public_token", ""))
    if not public_token:
        return jsonify({"error": "missing Link result"}), 400
    client = plaid_source.PlaidClient()
    result = client.exchange_public_token(public_token)
    sheet = _open_plaid_sheet()
    store = plaid_source.SheetStateStore(sheet)
    state = store.load()
    if len(state.get("items", {})) >= plaid_source.MAX_ITEMS:
        return (
            jsonify(
                {
                    "error": "Plaid Item limit reached",
                    "error_code": "item_limit_reached",
                }
            ),
            409,
        )
    item_id = str(result["item_id"])
    added, modified, removed, cursor = client.sync(str(result["access_token"]))
    # Keep the initial batch encrypted until the user reviews the bounded result.
    txns = added + modified
    linked_accounts = client.accounts(str(result["access_token"]))
    item = {
        "access_token": result["access_token"],
        "cursor": cursor,
        "status": "pending_review",
        "selected_account_ids": [
            str(account["account_id"]) for account in linked_accounts
        ],
        "account_mappings": {
            str(account["account_id"]): str(
                account.get("name") or account.get("official_name") or "Unknown Account"
            )
            for account in linked_accounts
        },
        "account_original_names": {
            str(account["account_id"]): str(
                account.get("name") or account.get("official_name") or "Unknown Account"
            )
            for account in linked_accounts
        },
        "pending_transactions": txns,
        "created_at": _utc_now(),
        "last_sync_at": "",
        "last_error": "",
    }
    existing = sheet.worksheet_by_title(
        title=config.GLOBAL.RAW_TRANSACTIONS_TITLE
    ).get_as_df(numerize=False)
    review = plaid_source.reconcile(
        existing.reindex(columns=config.GLOBAL.COLUMN_NAMES, fill_value=""),
        plaid_source.transaction_frame(txns, item),
    )
    item["reconciliation"] = review
    state.setdefault("items", {})[item_id] = item
    store.save(state)
    session["plaid_pending_item_id"] = item_id
    return jsonify(
        {
            "item_id": item_id,
            "review": review,
            "message": "Initial reconciliation stored; approve after reviewing it.",
        }
    )


@app.get("/plaid/review")
def plaid_review() -> Response | tuple[Response, int]:
    """Show the staged reconciliation before allowing an initial merge."""
    if not session.get("plaid_link_authorized") and not is_authorized_token(
        _request_token()
    ):
        return _forbidden()
    state = plaid_source.SheetStateStore(_open_plaid_sheet()).load()
    item_id = str(session.get("plaid_pending_item_id", ""))
    item = state.get("items", {}).get(item_id)
    if not item or item.get("status") != "pending_review":
        pending = [
            (stored_id, stored_item)
            for stored_id, stored_item in state.get("items", {}).items()
            if stored_item.get("status") == "pending_review"
        ]
        if len(pending) != 1:
            return jsonify({"error": "No unambiguous pending Plaid review"}), 404
        item_id, item = pending[0]
    review = item.get("reconciliation", {})
    raw_accounts = (
        _open_plaid_sheet()
        .worksheet_by_title(title=config.GLOBAL.RAW_TRANSACTIONS_TITLE)
        .get_as_df(numerize=False)
        .get("Account", [])
    )
    known_accounts = sorted(
        {str(account).strip() for account in raw_accounts if str(account).strip()}
    )
    original_names = item.get("account_original_names", {})
    accounts = [
        {
            "id": account_id,
            "plaid_name": original_names.get(account_id, account_name),
            "canonical_name": account_name,
            "selected": account_id in item.get("selected_account_ids", []),
        }
        for account_id, account_name in item.get("account_mappings", {}).items()
    ]
    return Response(
        render_template_string(
            """<!doctype html><title>Plaid import review</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:light;font-family:Inter,ui-sans-serif,system-ui,sans-serif;
--ink:#14213d;--muted:#667085;--line:#e6eaf0;--canvas:#f6f8fb;--mint:#0e7a62;
--mint-soft:#e9f7f2;--amber:#a15c07;--amber-soft:#fff5e5}
*{box-sizing:border-box}body{margin:0;background:var(--canvas);color:var(--ink)}
main{max-width:900px;margin:auto;padding:48px 24px 80px}.eyebrow{color:var(--mint);
font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
h1{font-size:36px;letter-spacing:-.04em;margin:8px 0 10px}.lede{color:var(--muted);
font-size:17px;line-height:1.55;margin:0 0 30px}.card{background:white;border:1px solid
var(--line);border-radius:18px;padding:24px;margin:18px 0;
box-shadow:0 8px 25px #14213d08}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric{padding:16px;
background:#fbfcfe;border:1px solid var(--line);border-radius:14px}
.metric b{display:block;
font-size:28px;letter-spacing:-.04em}.metric span{font-size:12px;color:var(--muted)}
.notice{background:var(--amber-soft);border:1px solid #f4d7a5;
border-radius:12px;padding:14px;
color:#754507;line-height:1.45}.account{display:grid;grid-template-columns:28px 1fr 1fr;
gap:14px;align-items:center;border-top:1px solid var(--line);padding:18px 0}
.account:first-of-type{border-top:0}.account input[type=checkbox]{width:18px;
height:18px;accent-color:var(--mint)}.plaid-name{font-weight:700}
.subtle{font-size:13px;color:var(--muted);margin-top:3px}
.field label{display:block;font-size:12px;font-weight:700;margin-bottom:6px}
.field select,.field input{width:100%;border:1px solid #cfd6e1;border-radius:9px;
padding:10px 11px;
font:inherit;color:var(--ink)}.actions{display:flex;gap:12px;align-items:center;
margin-top:22px}button{border:0;border-radius:10px;padding:11px 15px;
font:inherit;font-weight:750;cursor:pointer}
.secondary{background:#edf1f6;color:var(--ink)}
.primary{background:var(--mint);color:white}
.primary:disabled{opacity:.45;cursor:not-allowed}#result{color:var(--muted);margin:0}
@media(max-width:680px){main{padding:28px 16px}
.metrics{grid-template-columns:repeat(2,1fr)}
.account{grid-template-columns:25px 1fr}.field{grid-column:2}
.actions{align-items:stretch;
flex-direction:column}button{width:100%}}
</style><main>
<div class="eyebrow">Plaid · staged import</div><h1>Review with confidence.</h1>
<p class="lede">This 90-day import is staged only. Saving account choices updates the
reconciliation; approval is the only action that writes new transaction rows.</p>
<section class="metrics">
<div class="metric"><b>{{ review.matched_overlap }}</b><span>already in Sheet</span>
</div><div class="metric"><b>{{ review.plaid_only_candidates }}</b>
<span>new candidates</span>
</div><div class="metric"><b>{{ review.ambiguous_matches }}</b>
<span>ambiguous matches</span>
</div><div class="metric"><b>{{ review.account_mapping_gaps }}</b>
<span>mapping gaps</span></div>
</section><section class="card"><h2>Choose accounts and canonical names</h2>
<p class="lede">Choose an existing Sheet label from the menu, or use a new one.</p>
{% for account in accounts %}<div class="account"><input type="checkbox"
value="{{ account.id }}" {% if account.selected %}checked{% endif %}>
<div><div class="plaid-name">{{ account.plaid_name }}</div>
<div class="subtle">Connected through Plaid</div></div><div class="field">
<label>Use in Sheet as</label>
<select class="mapping-picker" data-account="{{ account.id }}">
{% for name in known_accounts %}<option value="{{ name }}"
{% if name == account.canonical_name %}selected{% endif %}>{{ name }}</option>
{% endfor %}<option value="__custom__"
{% if account.canonical_name not in known_accounts %}selected{% endif %}>
Use a new name…</option>
</select><input class="mapping custom-name" data-account="{{ account.id }}"
{% if account.canonical_name not in known_accounts %}
value="{{ account.canonical_name }}" placeholder="New Sheet account name">
{% else %}value="" hidden placeholder="New Sheet account name">{% endif %}
</div></div>{% endfor %}
<div class="actions"><button class="secondary" id="selection">
Save account choices</button>
<span id="result"></span></div></section><section class="card"><h2>Ready to merge?</h2>
<div class="notice">Approve only after confirming the selected accounts and the
candidate count. This appends only non-overlapping Plaid transactions.</div>
<div class="actions"><button class="primary" id="approve">
Approve initial merge</button></div>
</section></main><script>
function selected(){return [...document.querySelectorAll('input:checked')]
.map(x=>x.value)}
function mappings(){const values={};for(const picker of
document.querySelectorAll('.mapping-picker')){const custom=
picker.parentElement.querySelector('.custom-name');values[picker.dataset.account]=
picker.value==='__custom__'?custom.value:picker.value}return values}
for(const picker of document.querySelectorAll('.mapping-picker'))picker.onchange=()=>{
  const custom=picker.parentElement.querySelector('.custom-name');
  custom.hidden=picker.value!=='__custom__';if(!custom.hidden)custom.focus()
}
document.getElementById('selection').onclick=async()=>{const r=await fetch(
'/plaid/selection/{{ item_id }}',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({account_ids:selected(),account_mappings:mappings()})});
const p=await r.json();document.getElementById('result').textContent=
p.message||p.error||'Could not save.';if(r.ok)location.reload()}
const approve=document.getElementById('approve');let approvalPoll;
const approvalStatusUrl='/plaid/approve/{{ item_id }}/status';
async function approvalStatus(){
const r=await fetch(approvalStatusUrl+window.location.search);
const p=await r.json();if(p.state==='active'){clearInterval(approvalPoll);
approve.disabled=true;document.getElementById('result').textContent=
'Merged successfully. You may close this page.'}}
approve.onclick=async()=>{approve.disabled=true;
document.getElementById('result').textContent='Merging safely into Google Sheets…';
approvalPoll=setInterval(approvalStatus,5000);try{const r=await fetch(
'/plaid/approve/{{ item_id }}'+window.location.search,{method:'POST'});
const p=await r.json();
document.getElementById('result').textContent=p.message||p.error||'Could not approve.';
if(!r.ok){clearInterval(approvalPoll);approve.disabled=false}}catch(error){
document.getElementById('result').textContent='Connection interrupted. Do not retry; '+
'this page is checking merge status.'}}
</script>""",
            item_id=item_id,
            review=review,
            accounts=accounts,
            known_accounts=known_accounts,
        )
    )


@app.post("/plaid/selection/<item_id>")
def plaid_selection(item_id: str) -> Response | tuple[Response, int]:
    if not session.get("plaid_link_authorized") and not is_authorized_token(
        _request_token()
    ):
        return _forbidden()
    requested = (request.get_json(silent=True) or {}).get("account_ids", [])
    mappings = (request.get_json(silent=True) or {}).get("account_mappings", {})
    if not isinstance(requested, list):
        return jsonify({"error": "account_ids must be a list"}), 400
    if not isinstance(mappings, dict):
        return jsonify({"error": "account_mappings must be an object"}), 400
    sheet = _open_plaid_sheet()
    store = plaid_source.SheetStateStore(sheet)
    state = store.load()
    item = state.get("items", {}).get(item_id)
    if not item or item.get("status") != "pending_review":
        return jsonify({"error": "No pending initial reconciliation"}), 404
    available = set(item.get("account_mappings", {}))
    selected = [
        str(account_id) for account_id in requested if str(account_id) in available
    ]
    if not selected:
        return jsonify({"error": "Select at least one linked account"}), 400
    item["account_mappings"] = {
        account_id: str(mappings.get(account_id, current_name)).strip() or current_name
        for account_id, current_name in item.get("account_mappings", {}).items()
    }
    item["selected_account_ids"] = selected
    existing = (
        sheet.worksheet_by_title(title=config.GLOBAL.RAW_TRANSACTIONS_TITLE)
        .get_as_df(numerize=False)
        .reindex(columns=config.GLOBAL.COLUMN_NAMES, fill_value="")
    )
    item["reconciliation"] = plaid_source.reconcile(
        existing,
        plaid_source.transaction_frame(item.get("pending_transactions", []), item),
    )
    state["items"][item_id] = item
    store.save(state)
    return jsonify({"message": "Selected accounts and reconciliation updated."})


@app.get("/plaid/reauth/<item_id>")
def plaid_reauth(item_id: str) -> Response | tuple[Response, int]:
    if not is_authorized_token(_request_token()):
        return _forbidden()
    unavailable = _require_plaid_configured()
    if unavailable:
        return unavailable
    state = plaid_source.SheetStateStore(_open_plaid_sheet()).load()
    item = state.get("items", {}).get(item_id)
    if not item:
        return jsonify({"error": "Plaid Item not found"}), 404
    link = plaid_source.PlaidClient().create_link_token(
        update_access_token=str(item["access_token"])
    )
    session["plaid_reauth_item_id"] = item_id
    return Response(
        render_template_string(
            """<script src="//cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<p>Reauthenticating account…</p><script>
Plaid.create({token: {{ token|tojson }}, onSuccess: async () => {
  const response = await fetch('/plaid/reauth/complete', {method: 'POST'});
  document.body.innerText = (await response.json()).message || 'Updated.';
}}).open();</script>""",
            token=link["link_token"],
        )
    )


@app.post("/plaid/reauth/complete")
def plaid_reauth_complete() -> Response | tuple[Response, int]:
    item_id = session.pop("plaid_reauth_item_id", "")
    if not item_id:
        return _forbidden()
    store = plaid_source.SheetStateStore(_open_plaid_sheet())
    state = store.load()
    item = state.get("items", {}).get(item_id)
    if not item:
        return jsonify({"error": "Plaid Item not found"}), 404
    item["status"] = "active"
    item["last_error"] = ""
    state["items"][item_id] = item
    store.save(state)
    return jsonify({"message": "Plaid connection reauthenticated."})


@app.post("/plaid/approve/<item_id>")
def plaid_approve(item_id: str) -> Response | tuple[Response, int]:
    if not session.get("plaid_link_authorized") and not is_authorized_token(
        _request_token()
    ):
        return _forbidden()
    if not _plaid_approval_lock.acquire(blocking=False):
        return (
            jsonify(
                {
                    "error": "An initial merge is already in progress.",
                    "error_code": "approval_in_progress",
                }
            ),
            409,
        )
    try:
        sheet = _open_plaid_sheet()
        store = plaid_source.SheetStateStore(sheet)
        state = store.load()
        item = state.get("items", {}).get(item_id)
        if not item:
            return jsonify({"error": "Plaid Item not found"}), 404
        if item.get("status") == "active":
            return jsonify({"message": "Initial Plaid merge already completed."})
        if item.get("status") not in {"pending_review", "merging"}:
            return jsonify({"error": "No pending initial reconciliation"}), 404

        # Persist intent before writing the raw tab. If the process restarts
        # mid-write, a later request can safely resume because merging is
        # idempotent under the source-independent overlap fingerprint.
        item["status"] = "merging"
        item["approval_started_at"] = _utc_now()
        item["last_error"] = ""
        state["items"][item_id] = item
        store.save(state)

        existing = (
            sheet.worksheet_by_title(title=config.GLOBAL.RAW_TRANSACTIONS_TITLE)
            .get_as_df(numerize=False)
            .reindex(columns=config.GLOBAL.COLUMN_NAMES, fill_value="")
        )
        additions = plaid_source.transaction_frame(
            item.get("pending_transactions", []), item
        )
        merged = plaid_source.merge_transactions(existing, additions, set(), set())
        remote.UpdateGoogleSheet(sheet, merged, None)

        item["status"] = "active"
        item["approved_at"] = _utc_now()
        item["pending_transactions"] = []
        state["items"][item_id] = item
        store.save(state)
        session.pop("plaid_link_authorized", None)
        session.pop("plaid_link_token", None)
        session.pop("plaid_pending_item_id", None)
        return jsonify(
            {
                "message": (
                    "Initial Plaid transactions merged and daily cursor sync enabled."
                )
            }
        )
    except Exception:
        logging.exception("Plaid initial merge failed")
        return (
            jsonify(
                {
                    "error": "Initial merge needs a safe retry.",
                    "error_code": "sync_failed",
                }
            ),
            502,
        )
    finally:
        _plaid_approval_lock.release()


@app.get("/plaid/approve/<item_id>/status")
def plaid_approve_status(item_id: str) -> Response | tuple[Response, int]:
    if not session.get("plaid_link_authorized") and not is_authorized_token(
        _request_token()
    ):
        return _forbidden()
    state = plaid_source.SheetStateStore(_open_plaid_sheet()).load()
    item = state.get("items", {}).get(item_id)
    if not item:
        return jsonify({"error": "Plaid Item not found"}), 404
    return jsonify(
        {
            "state": item.get("status", ""),
            "pending_transactions": len(item.get("pending_transactions", [])),
            "last_error": item.get("last_error", ""),
        }
    )


@app.get("/plaid/oauth/redirect")
def plaid_oauth_redirect() -> Response:
    # Plaid Link receives the registered URL and resumes in the same browser.
    token = session.get("plaid_link_token")
    if not token:
        return Response(
            "Plaid Link session expired; return to Sheets and start again.", status=400
        )
    return Response(
        render_template_string(
            """<script src="//cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<p>Resuming bank authentication…</p><script>
async function exchange(public_token) {
  const response = await fetch('/plaid/exchange', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({public_token})
  });
  document.body.innerText = (await response.json()).message || 'Connected.';
}
Plaid.create({token: {{ token|tojson }}, receivedRedirectUri: window.location.href,
  onSuccess: exchange}).open();
</script>""",
            token=token,
        )
    )
