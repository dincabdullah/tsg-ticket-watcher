#!/bin/bash
# Mac'te launchd ile yerel nöbetçi kurar. GitHub Actions'tan bağımsızdır.
#
#   bash local/install.sh          # 120 saniyede bir kontrol
#   bash local/install.sh 60       # 60 saniyede bir kontrol
#
# Kaldırmak için: bash local/uninstall.sh

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.tsg.ticketwatcher"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/tsg-ticket-watcher.log"
INTERVAL="${1:-120}"

if [ ! -f "$DIR/.env" ]; then
  echo "HATA: $DIR/.env yok."
  echo "  cp .env.example .env    yapıp token ve chat_id'yi doldur."
  exit 1
fi

echo "==> Sanal ortam hazırlanıyor"
python3 -m venv "$DIR/.venv" 2>/dev/null || true
"$DIR/.venv/bin/pip" install --quiet --upgrade pip requests

echo "==> Bir kez deneme çalıştırması"
(cd "$DIR" && "$DIR/.venv/bin/python" check_tickets.py --dry-run)

echo "==> launchd görevi yazılıyor ($INTERVAL saniyede bir)"
mkdir -p "$HOME/Library/LaunchAgents" "$(dirname "$LOG")"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>            <string>$LABEL</string>
  <key>WorkingDirectory</key> <string>$DIR</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/.venv/bin/python</string>
    <string>$DIR/check_tickets.py</string>
  </array>
  <key>StartInterval</key>    <integer>$INTERVAL</integer>
  <key>RunAtLoad</key>        <true/>
  <key>StandardOutPath</key>  <string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLISTEOF

launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl kickstart -k "gui/$UID/$LABEL"

echo
echo "Kuruldu. Kontrol her $INTERVAL saniyede bir çalışacak."
echo "Canlı log:  tail -f $LOG"
echo "Durdurmak:  bash local/uninstall.sh"
echo
echo "NOT: Mac uyursa kontrol durur, uyanınca kaldığı yerden devam eder."
echo "     Sürekli açık tutmak için ayrı bir terminalde: caffeinate -i"
