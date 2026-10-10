# Running Daleel for a demo

The demo runs on **one laptop** (the teammate's MacBook) with a tunnel for the public HTTPS URL that Twilio
and the judges' phones reach. The AWS server at the bottom is the fallback.

## A. The demo laptop (macOS or Linux)
Install first: **Docker Desktop** (or OrbStack) and start it, **Ollama** (https://ollama.com) and open it,
**Python 3.12** (`brew install python@3.12`), and a tunnel: `brew install ngrok` or `brew install cloudflared`.

```bash
git clone <repo> && cd hack4health
bash infra/laptop_setup.sh      # once: .env, database, packages, seed data, the model; ends with "ready"
bash infra/run_demo.sh          # terminal 1: the app on 127.0.0.1:8000 + the retention loop. Ctrl-C stops both
```
`laptop_setup.sh` is safe to re-run (after every `git pull`). It creates `.env` with demo settings if there is
none, pulls the model named by `DALEEL_MODEL` in `.env` (`qwen2.5:7b`, about 4.7 GB), and stops with `FAILED:`
if Docker or Ollama is not running, the database is unhealthy, or a stub provider would be live.
It prints row counts: **`procedures: 0 rows` means B's ingestion still has to be run on this laptop**
(`PYTHONPATH=src .venv/bin/python src/ai/ingest.py URL [URL ...]`), otherwise procedure questions get the hotline reply.

**Public URL (terminal 2).** Pick one:
```bash
ngrok http --url=<your-name>.ngrok-free.app 8000     # free account gives ONE fixed domain: set it once in Twilio
cloudflared tunnel --url http://localhost:8000       # no account, but a NEW url on every restart
```
ngrok shows browsers a one-time "you are about to visit" page; WhatsApp webhooks are not affected.
Then put the URL in `.env` as `PUBLIC_BASE_URL=https://...` (no trailing slash), add the Twilio values,
restart `run_demo.sh`, and set the Twilio sandbox webhook to `https://<public-url>/webhook/whatsapp` (POST).

**Check it from a phone on mobile data:** `https://<public-url>/health` returns `{"ok":true,...}`, and
`https://<public-url>/health/channels` shows no provider starting with `Stub`.

Keep the laptop plugged in with the lid open (`run_demo.sh` stops macOS sleeping while it runs).
**Never run `pytest` on the demo laptop**: the DB tests reload seed tables and delete transcripts
(`DALEEL_ENV=production` in its `.env` makes the suite refuse). Nothing limits request size on a tunnel.

## Settings that matter (`.env`)
| Setting | Demo value | Why |
|---|---|---|
| `SESSION_HASH_SALT` | any long random string | with the default `change-me`, no transcript rows are stored |
| `STORE_TRANSCRIPT_TEXT` | `1` | keep scrubbed text so the deletion can be shown; default is off |
| `RETENTION_IDLE_MINUTES` / `RETENTION_INTERVAL_SECONDS` | `2` / `20` | the deletion is visible within about two minutes |
| `PUBLIC_BASE_URL` | the public HTTPS URL | Twilio signs requests with this exact URL |
| `TWILIO_AUTH_TOKEN`, `TWILIO_ACCOUNT_SID`, `TWILIO_SANDBOX_JOIN_CODE` | from the Twilio console | WhatsApp |
| `REQUIRE_TWILIO_SIGNATURE`, `REQUIRE_META_SIGNATURE` | `true` on anything public | otherwise anyone can post as any phone number |

Twilio sandbox webhook: `https://<public-url>/webhook/whatsapp`, method POST.

## Before each rehearsal
```bash
bash infra/reset_demo.sh                              # clears transcripts + metadata, adds 320 SAMPLE metadata rows
PYTHONPATH=src python -m data.retention --status      # exit 1 if any session is overdue for deletion
```
The sample rows are made up (marked `subtopic = 'sample'`); say so when showing the dashboard.

## Showing the privacy flow
```bash
docker compose exec db psql -U daleel -c "SELECT turn, role, text FROM transcripts ORDER BY created_at"
PYTHONPATH=src python -m data.retention --once        # or wait for the loop
```
Honest wording: transcripts are temporary, masked (phone numbers, IDs, emails, introduced names — not a
bare name or an address) and deleted from the live database after the idle window, 24 hours at most.
Copies held by WhatsApp, Twilio, the model provider and the user's phone are outside our control.

## B. Fallback: the AWS server
One Ubuntu 24.04 server built by `infra/vm_setup.sh` (Postgres, the app, the retention loop, Ollama with the
smaller `qwen2.5:3b`, Caddy for HTTPS). It is slower and answers less well than the laptop. D has the SSH access.
```bash
HOST=ubuntu@<server-ip>
rsync -az --delete --exclude .venv --exclude .git --exclude __pycache__ --exclude .env --exclude .pytest_cache ./ $HOST:/opt/daleel/
ssh $HOST 'bash /opt/daleel/infra/vm_setup.sh <a-b-c-d>.sslip.io'     # first time; the server IP with dashes
ssh $HOST 'sudo systemctl restart daleel-app daleel-retention'         # after later rsyncs
```
