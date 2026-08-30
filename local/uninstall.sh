#!/bin/bash
# Yerel launchd nöbetçisini kaldırır.
set -euo pipefail
LABEL="com.tsg.ticketwatcher"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
echo "Yerel nöbetçi kaldırıldı."
