# Running Daleel for a demo

Two ways to run it. Both end with a public HTTPS URL that Twilio and the judges' phones can reach.

## A. Cloud server (what is deployed now)
One Ubuntu 24.04 server, built by `infra/vm_setup.sh`. It runs Postgres (docker, loopback only), the app,
the retention loop, a small local model (Ollama) and Caddy for HTTPS.

```bash
# from your laptop, in the repo root
HOST=ubuntu@<server-ip>
ssh $HOST 'sudo mkdir -p /opt/daleel && sudo chown ubuntu:ubuntu /opt/daleel'
rsync -az --delete --exclude .venv --exclude .git --exclude data_source --exclude __pycache__ \
      --exclude .env --exclude .pytest_cache ./ $HOST:/opt/daleel/
ssh $HOST 'bash /opt/daleel/infra/vm_setup.sh <a-b-c-d>.sslip.io'     # the server IP with dashes
```
`<ip-with-dashes>.sslip.io` resolves to the server and gets a real certificate, so no domain is needed.
The script is safe to re-run; it stops with `FAILED:` if the database is unhealthy or a stub provider is live.

**Update after a `git pull`:** rsync again, then `ssh $HOST 'sudo systemctl restart daleel-app daleel-retention'`.

**Never run `pytest` on the server.** The DB tests reload seed tables and delete idle transcripts.
(`DALEEL_ENV=production` in the server's `.env` makes the suite refuse.)

## B. A laptop plus a tunnel
```bash
docker compose up -d
PYTHONPATH=src python -m data.db && PYTHONPATH=src python -m data.loaders
PYTHONPATH=src uvicorn core.app:app --host 127.0.0.1 --port 8000      # terminal 1
PYTHONPATH=src python -m data.retention --loop                         # terminal 2
cloudflared tunnel --url http://localhost:8000                         # terminal 3: prints the public URL
```
The tunnel URL changes every time it restarts.

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
