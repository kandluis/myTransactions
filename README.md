# Set-Up

## Environment Variables

To setup the scraper, you need to follow the following steps.

First, a `.env` file at the top-level directory needs to exists. It should look like:

```sh
ACCOUNT_USERNAME=<TODO>
PASSWORD=<TODO>
MFA_TOKEN=<TODO>
GOOGLE_SHEETS_CREDENTIALS=<TODO> // The keys.json file for the Google sheets service, as a string.
```
Note that MFA_TOKEN is needed for Mint accounts with 2-FA enabled, and corresponds to the token that Google Authenticator uses. With this token, the app can generate OTP on its own. If not provided, we will fall-back to text-based method and this will require user interaction.


Additionally, you need a `keys.json` file containing valid keys to be used when accessing the Google Spreadsheet. This is just a JSON file that you should be able to download from the Google Cloud Console. You need to attach in the `GOOGLE_SHEETS_CREDENTIALS` section above as a single string.

Note that we rely on `pipenv` to automatically load the variables from `.env` into your environment. If you are not using `pipenv`, you will need to load them in some other way.


## Python Requirements

### `pipenv` and `pyenv`

As of the latest update, we recommend leveraging `pipenv` and `pyenv` to maintain a hermetic static for dependencies. The other options are left here only for reference as they are not maintained/tested often.

On Mac, make sure you have [Homebrew](https://brew.sh/) installed. You can install `pipenv` and `pyenv` with:

```sh
brew install pipenv
brew install pyenv
```

After installing, you navigate to the root of the project directory, and run:

```sh
pipenv install
```

This will install all the required dependencies as well as the appropriate Python version (using pyenv). You can then run:

```sh
pipenv run python scraper.py --types=all
```

To run the script with these installs, or you can jump into the installed Python environment at the shell bevel with:

```sh
pipenv shell
```

# Scripts

## Scrape Transactions and Accounts

Use `scraper.py` to retrieve data from Empower and write it to the configured
Google Sheet.

```sh
pipenv run python scraper.py --types=all
```

The `--types` option can be one of:

- `all`: scrape transactions and accounts.
- `transactions`: scrape only transactions.
- `accounts`: scrape only accounts.

Useful flags:

- `--dry_run`: retrieve and process data without updating Google Sheets.
- `--debug`: write local CSV snapshots such as `transactions.csv` and
  `accounts.csv`.

Example:

```sh
pipenv run python scraper.py --types='transactions' --dry_run --debug
```

## Reapply Category Rules

Use `updater.py` when transaction data already exists in Google Sheets and you
want to reapply the category rules in `config.yaml` without scraping new data.
This is the safest way to validate category-map changes before writing them
back to the sheet.

```sh
pipenv run python updater.py --dry_run
```

In dry-run mode, the updater writes `transactions_updated.csv` locally and does
not update Google Sheets. After reviewing the output, run without `--dry_run` to
write the cleaned transactions back:

```sh
pipenv run python updater.py
```

Use `--debug` with a real update to also write `transactions_updated.csv`.

## Generate Interactive Spend Charts

Use `scripts/generate_spend_charts.py` to create an interactive Plotly HTML
profile of historical spend by category. The report includes a total rolling
spend trend, a stacked rolling category view, a 100% stacked rolling category
share view, and a monthly category heatmap. Categories are assigned with the
same rules in `config.yaml` used by `updater.py`; the chart script does not
maintain separate hard-coded plotting categories.

The safest local flow is to first generate a cleaned CSV without writing
changes back to Google Sheets:

```sh
pipenv run python updater.py --dry_run
```

This writes `transactions_updated.csv`, which the chart generator uses by
default:

```sh
pipenv run python scripts/generate_spend_charts.py
```

By default, the chart keeps the top 10 categories and groups the rest as
`Other` so hover labels stay usable. You can also pass another CSV path and tune
the rolling-average window or category display:

```sh
pipenv run python scripts/generate_spend_charts.py --input data/transactions.csv --window 31 --top-n-categories 12
```

The normalized share chart is based on rolling displayed spend, so it uses the
same smoothing and visual capping as the absolute rolling category chart. Days
with no displayed rolling spend are shown as gaps instead of a misleading
category mix.

For faster local memory iteration on the chart pipeline, use the benchmark
script. It runs in-process against a local cached export of the full Sheet
transaction list when available, and prints elapsed time and peak RSS as JSON:

```sh
pipenv run python scripts/benchmark_spend_chart.py --refresh-from-sheets
```

The first run can refresh `data/benchmark_transactions.csv` from Sheets. After
that, the benchmark reuses that cached export automatically. You can also point
it at another CSV and keep the output if you want to inspect the generated
HTML:

```sh
pipenv run python scripts/benchmark_spend_chart.py \
  --input /path/to/transactions.csv \
  --output /tmp/spend-profile.html
```

To compare memory across the compact report variants, run the 8-way sweep:

```sh
pipenv run python scripts/benchmark_spend_chart.py \
  --sweep-compact-matrix \
  --input data/benchmark_transactions.csv
```

For datasets with large one-off expenses, the chart applies an automatic
visual-only cap to unusually large daily category totals. The cap affects chart
scaling and rolling averages, while hover labels and outlier reports keep the
raw values available for review. You can override the automatic cap and write an
outlier CSV:

```sh
pipenv run python scripts/generate_spend_charts.py --cap-daily-spend 1000 --outlier-report outliers.csv
```

To read transactions directly from the configured Google Sheet, use Sheets mode:

```sh
pipenv run python scripts/generate_spend_charts.py --source sheets --output spend_profile.html
```

Useful flags:

- `--output`: HTML output path, defaulting to `spend_profile.html`.
- `--start-date` and `--end-date`: limit the chart to a date range.
- `--exclude-category`: omit a category; repeat the flag for multiple
  categories.
- `--top-n-categories`: keep the largest categories and group the rest as
  `Other`; defaults to `10`.
- `--cap-daily-spend`: override the automatic cap for displayed daily category
  spend before rolling averages, without changing raw spend values.
- `--no-auto-cap`: disable the automatic visual cap.
- `--outlier-report`: write a CSV of transactions on capped or statistically
  unusual high-spend days.
- `--skip-cleanup`: keep ignored categories/accounts in the chart for debugging.

## Publish Hosted Spend Report

Use `scripts/publish_spend_report.py` to generate both `spend_profile.html` and
`outliers.csv` into a directory for serving. On Fly, the web service stores
these files under `/data/reports` so they survive restarts.

```sh
REPORT_TOKEN=<secret> REPORT_BASE_URL=https://mint-scraper.fly.dev \
  pipenv run python scripts/publish_spend_report.py --source sheets --update-sheet
```

For local testing:

```sh
pipenv run python scripts/publish_spend_report.py \
  --source sheets \
  --output-dir /tmp/spend-report \
  --base-url http://localhost:8080 \
  --token test \
  --update-sheet
```

The publisher writes report status to `Settings!F1:G6`, including the latest
tokenized report URLs, generation timestamp, status, source, and error text.
If generation fails, it preserves the last successful report URLs when they are
already present in the sheet.
The `/generate` endpoint returns immediately and uses the compact report mode
without the monthly heatmap. The background job writes the sheet status when
it finishes. The normal CLI and local chart generation still produce the full
report by default.

## Trigger Scraper From Sheets

Use `POST /scrape?token=<REPORT_TOKEN>` to kick off a background scraper run
against the live sheet. The endpoint checks `Settings!D5` first and skips the
run when the last successful scrape is still within the freshness window
(`15` minutes by default). When a scrape succeeds, the app writes a
machine-readable UTC timestamp into `Settings!D5` so both the endpoint and a
Sheets script can make the same freshness decision.

The scrape job reuses the existing scraper flow and the shared `REPORT_TOKEN`.
It is safe to invoke from a menu item or button in Google Sheets:

```javascript
function triggerScrape() {
  const token = PropertiesService.getScriptProperties().getProperty('REPORT_TOKEN');
  const url = 'https://mint-scraper.fly.dev/scrape?token=' + encodeURIComponent(token);
  const response = UrlFetchApp.fetch(url, { method: 'post', muteHttpExceptions: true });
  if (response.getResponseCode() >= 300) {
    throw new Error(response.getContentText());
  }
}
```

You can optionally read `Settings!D5` in Apps Script first and skip the
network call when the scrape is already fresh. The server still enforces the
freshness check and prevents overlapping runs with the scheduled scraper.

The Fly web service exposes:

- `GET /health`: unauthenticated health check.
- `POST /generate?token=<REPORT_TOKEN>`: enqueue report generation from Sheets
  and return `202` immediately.
- `GET /generate/status?token=<REPORT_TOKEN>`: poll the latest job state and
  result after enqueueing.
- `GET /reports/spend_profile.html?token=<REPORT_TOKEN>`: open the latest
  HTML report.
- `GET /reports/outliers.csv?token=<REPORT_TOKEN>`: download the latest
  outlier CSV.
- `POST /scrape?token=<REPORT_TOKEN>`: enqueue a scraper run when the last
  successful scrape is stale enough.
- `GET /scrape/status?token=<REPORT_TOKEN>`: poll the latest scrape job state.

Set Fly secrets before deploying:

```sh
fly secrets set REPORT_TOKEN=<secret> REPORT_BASE_URL=https://mint-scraper.fly.dev
fly deploy
```

To trigger generation from Google Sheets, add this optional Apps Script and
bind `generateSpendReport` to a drawing, button, or custom menu:

```javascript
function generateSpendReport() {
  const token = PropertiesService.getScriptProperties().getProperty('REPORT_TOKEN');
  const url = 'https://mint-scraper.fly.dev/generate?token=' + encodeURIComponent(token);
  const response = UrlFetchApp.fetch(url, { method: 'post', muteHttpExceptions: true });
  if (response.getResponseCode() >= 300) {
    throw new Error(response.getContentText());
  }
}
```

## Generate Merchant Category Maps

Use `scripts/generate_keyword_map.py` to refresh category coverage from the
merchant list in `data/unique_merchants.csv`.

```sh
pipenv run python scripts/generate_keyword_map.py
```

The generator reads:

- `config.yaml`: the existing keyword category map.
- `data/unique_merchants.csv`: unique merchants to measure coverage against.
  The file may be a single-column CSV or include a `merchant` header.
- `data/merchant_category_overrides_2025_2026.yaml`: curated labels for known
  merchants that are not reliably handled by broad keywords.

It updates two sections in `config.yaml`:

- `MERCHANT_TO_CATEGORY_MAP`: reusable keyword-based rules.
- `EXACT_MERCHANT_TO_CATEGORY_MAP`: exact fallback rules for merchants still
  not covered by keywords.

After running the generator, review the `config.yaml` diff. Keywords should be
reusable merchant or category signals; one-off or artifact-like names should
stay in the exact map instead.

Recommended validation flow:

```sh
pipenv run python scripts/generate_keyword_map.py
pipenv run python updater.py --dry_run
pipenv run pytest
```

# Type Checking

For development purposes, you want to also install the dev dependencies by running `pipenv install -d`.

You should be able to type check by running:

```sh
pipenv run mypy .
```

# Unit Tests

You can run all unit tests with the command:
```sh
pipenv run pytest
```

# Formatting

You can run all formatting with the command:
```sh
pipenv run black .
```

# CI Checks

GitHub Actions runs formatting, linting, type checking, and tests. To run the
same local checks before pushing:

```sh
pipenv run black . --check
pipenv run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
pipenv run flake8 . --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics
pipenv run mypy .
pipenv run pytest --cov --cov-report=xml
```

# Deploy to fly.io

## Setup

The first thing you want to do is install `flyctl`. You can do this on Mac trivially if you have `brew` installed using:

```sh
brew install flyctl
```

## Deployment
We migrated our Heroku stack. We now leverage a custom-built Docker container that gets deployed to `fly.io` for our purposes. 

The deployment of the container should happen automatically using Github actions whenever you push the repo. Just leverage that.

### Wait, I need to deploy manualyl!

We recommend you build it remotely. This happens by default when simply running. You can install `flyctl` with `brew install flyctl`:

```sh
flyctl deploy --remote-only
```

### Testing Locally
You can build this container locally and run it:
```sh
docker build -t mint_scraper .
```

Once built, you can test locally by running the image. Note that it might fail due to binary incompatibitlies between the driver versions.
```sh
docker run --env-file=.env mint_scraper:latest python scraper.py --types=all
```

## Managing 2FA Session on Fly.io

The scraper relies on a persistent session file to bypass 2FA. If the session expires, you need to refresh it manually.

1.  **Run Locally:** Execute the scraper locally to complete the 2FA challenge. This generates a valid `.session.pkl` file in your directory.
2.  **Find VM:** Identify the Fly Machine attached to your volume:
    ```sh
    fly volumes list
    ```
    Copy the `ATTACHED VM` ID (e.g., `9080e52b`).
3.  **Sleep Machine:** Update the machine to run a sleep command so it stays alive for maintenance:
    ```sh
    fly machine update <VM_ID> --entrypoint /bin/sleep --command infinity
    ```
4.  **Start Machine:**
    ```sh
    fly machine start <VM_ID>
    ```
5.  **Upload Session:** Connect via SFTP and upload the new session file:
    ```sh
    fly sftp shell -s <VM_ID>
    >> put .session.pkl /data/.session.pkl
    >> exit
    ```
6.  **Restore:** Redeploy the app to reset the machine to its normal scraper command:
    ```sh
    fly deploy
    ```

## Debugging

If you're running into issues, you want to debug by ssh'ing into the machine. 

1. Download and install [Wireguard](https://www.wireguard.com/install/).
2. Run `flyctl wireguard create` and use the output config for a new tunnel in Wireguard. Activate this tunnel.
3. Run `flyctl ssh issue --agent` to populate a 24hr certificate in your local agent.
4. RUn `flyctl ssh console --app mint-scraper-fly`

For the last command, you can replace `mint-scraper-fly` with the name of the app. This will connect to a running instance of `mint-scraper-fly` using a basic shell. You can now debug to your heart's content.


# Version

3.0.0
