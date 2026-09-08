#!/usr/bin/env bash
# Launch the Chrome instance the MCP server attaches to.
# A dedicated profile is required: without it Chrome hands the request to
# your already-running instance and never opens the debug port.
set -euo pipefail
PORT="${FLOW_CDP_PORT:-9222}"
PROFILE="${FLOW_CHROME_PROFILE:-$HOME/.flow-mcp-profile}"

if curl -s --max-time 2 "http://localhost:$PORT/json/version" >/dev/null 2>&1; then
  echo "Chrome zaten $PORT portunda dinliyor."
  exit 0
fi

echo "Chrome aciliyor (profil: $PROFILE)"
echo "Ilk acilista Google hesabina elle giris yap, sonra flow.google.com'da bir proje ac."
exec "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE"
