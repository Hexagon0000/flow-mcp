#!/usr/bin/env bash
# Start the debug Chrome at login so the MCP server always has something
# to attach to.
set -euo pipefail

LABEL="com.flow-mcp.chrome"
PROFILE="${FLOW_CHROME_PROFILE:-$HOME/.flow-mcp-profile}"
LOGDIR="$HOME/Library/Logs/flow-mcp"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SRC="$(cd "$(dirname "$0")" && pwd)/$LABEL.plist"

mkdir -p "$LOGDIR" "$(dirname "$PLIST")"
sed -e "s|__PROFILE__|$PROFILE|" -e "s|__LOGDIR__|$LOGDIR|" "$SRC" > "$PLIST"

# Replace any previous registration before loading the new one.
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"

echo "Yuklendi: $PLIST"
echo "Profil  : $PROFILE"
echo "Loglar  : $LOGDIR"
echo
echo "Kaldirmak icin: launchctl bootout gui/$UID/$LABEL && rm $PLIST"
