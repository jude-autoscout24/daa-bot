# Terminland Appointment Watcher (DAA Muenchen Deutschkurse)

Small service that checks the Terminland booking page and emails you when availability changes. It uses Playwright for a JS-heavy site, stores state in SQLite, and rate-limits checks with jitter and backoff.

## Setup

1) Create and activate a Python 3.11+ virtual environment.
2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Install Playwright browsers:

```bash
python -m playwright install chromium
```

4) Create config and env files:

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

5) Set Gmail App Password (requires 2FA):
- Go to Google Account > Security > App passwords.
- Create an app password and paste it into `.env`.

## Running

Single check (prints normalized JSON):

```bash
python -m src.main check-once --config config.yaml
```

Run forever with scheduler/backoff:

```bash
python -m src.main run --config config.yaml
```

Test email (sends once and exits):

```bash
TEST_EMAIL=1 python -m src.main check-once --config config.yaml
```

Artifacts:
- SQLite DB: `./data/state.db`
- Screenshots: `./data/screenshots`
- HTML dumps: `./data/html`

Postgres (optional):
- Set `DATABASE_URL` (or update `storage.postgres_url_env`) to use Postgres instead of SQLite.
- Schema is created automatically on startup.

## Blocked or CAPTCHA

The checker will not bypass CAPTCHA or anti-bot challenges. If it detects blocking (403/429 or CAPTCHA text), it will cool down and send a "BLOCKED" email. Review the saved screenshot and HTML for clues.

## Optional endpoint checker

If you discover an XHR endpoint that returns availability, update `src/checker_endpoint.py` and set `target.mode: endpoint` in config. You can find potential endpoints by:
- Opening DevTools > Network
- Filtering by XHR/Fetch
- Looking for responses with dates or times

Playwright remains the default and must work even if no endpoint is found.

## Tests

```bash
pytest
```

## Render deployment (cron)

This repo includes a `Dockerfile` and `render.yaml` for a Render cron job that runs every 30 minutes.

Steps:
1) Push the repo to GitHub.
2) In Render, create a new Blueprint deployment from your repo.
3) Set environment variables `SMTP_USER` and `SMTP_PASS` in the Render dashboard.
4) Update `config.yaml` to set the `notify.email.from` and `notify.email.to` addresses you want.

Note: Render cron jobs use an ephemeral filesystem, so `./data/state.db` will not persist between runs. That means the watcher may send duplicate notifications if appointments become available. For persistent state, use a Render Web Service with a disk or switch to an external database.
If you attach a Render Postgres instance, set `DATABASE_URL` in the cron job env vars so the state persists.
