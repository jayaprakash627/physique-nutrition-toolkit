#!/usr/bin/env bash
#
# run.sh — start the toolkit on this machine.
#
#   ./run.sh
#
# Exists because the app deliberately reads real environment variables and does
# not parse .env itself (see .env.example). That's the right call for a server
# holding health data — but it means starting it by hand is a two-part command
# that's easy to get wrong. This does the loading for you.
#
# This is the LOCAL copy, for you only. The one your clients use is the deployed
# site, which is always running and needs nothing started.

set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "No virtualenv here yet. One-time setup:"
  echo
  echo "    python3 -m venv .venv"
  echo "    .venv/bin/pip install -r requirements.txt"
  echo
  exit 1
fi

# Load .env into the real environment, which is where the app looks.
if [[ -f .env ]]; then
  set -a; source ./.env; set +a
fi

if [[ -z "${COACH_PASSWORD:-}" ]]; then
  echo "⚠️  COACH_PASSWORD isn't set, so Coach mode will refuse to open."
  echo "   The calculator still works. To fix it, put a password in .env:"
  echo
  echo "       COACH_PASSWORD=$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')"
  echo
fi

if lsof -ti "tcp:$PORT" >/dev/null 2>&1; then
  echo "Port $PORT is already busy. Either something else is on it, or the"
  echo "toolkit is already running — try http://127.0.0.1:$PORT first."
  echo "To use a different port:  PORT=8010 ./run.sh"
  exit 1
fi

echo
echo "  Physique & Nutrition Toolkit — running on your Mac"
echo "  ────────────────────────────────────────────────────"
echo "  Open this:   http://127.0.0.1:$PORT"
echo "  Coach mode:  the password in your .env"
echo "  Database:    $([[ -n "${DATABASE_URL:-}" ]] && echo 'Neon (Postgres)' || echo 'local file — toolkit.db')"
echo
echo "  Press Control-C to stop it."
echo

exec .venv/bin/uvicorn app.main:app --reload --port "$PORT"
