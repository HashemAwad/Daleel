#!/usr/bin/env bash
# Keep the AWS front door pointed at this laptop. Owner: D.
#
#   WhatsApp -> Twilio -> https://13-51-237-14.sslip.io (AWS, Caddy) -> this tunnel -> the app on 127.0.0.1:8000
#
# Run in its own terminal next to infra/run_demo.sh and leave it open. Ctrl-C stops it.
# It reconnects by itself within a few seconds if the connection drops (Wi-Fi change, sleep, new IP).
# Needs: your SSH public key on the server (D adds it) and your public IP inside the server's firewall.
#   SERVER=ubuntu@13.51.237.14 PORT=8001 bash infra/tunnel_to_aws.sh     # both are overridable
set -u
SERVER="${SERVER:-ubuntu@13.51.237.14}"
PORT="${PORT:-8001}"                 # port on the server that Caddy forwards to; must match its Caddyfile
LOCAL="${LOCAL:-127.0.0.1:8000}"     # the app started by infra/run_demo.sh
trap 'echo; echo "tunnel stopped"; exit 0' INT TERM

while true; do
  echo "$(date +%H:%M:%S) tunnel up: server:$PORT -> $LOCAL   (Ctrl-C to stop)"
  ssh -N -R "127.0.0.1:$PORT:$LOCAL" \
      -o ExitOnForwardFailure=yes -o ServerAliveInterval=10 -o ServerAliveCountMax=3 \
      -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new -o BatchMode=yes "$SERVER"
  echo "$(date +%H:%M:%S) tunnel dropped (ssh exit $?); reconnecting in 3s"
  sleep 3
done
