#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ "${EUID:-$(id -u)}" != 0 ]]; then echo 'sudo bash uninstall.sh ile çalıştırın.';exit 1;fi
python3 - "$ROOT" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]).resolve()
assert p!=Path(p.anchor),'Kök dizin kaldırılamaz.'
assert json.loads((p/'installation.json').read_text())['product']=='Ufuk-FileAudit','Kurulum işareti doğrulanamadı.'
PY
systemctl disable --now ufuk-fileaudit-retention.timer 2>/dev/null || true
rm -f /etc/systemd/system/ufuk-fileaudit-retention.timer /etc/systemd/system/ufuk-fileaudit-retention.service
systemctl daemon-reload
docker compose --project-directory "$ROOT" down --remove-orphans
echo 'Web uygulaması ve temizleme görevi kaldırıldı. Veritabanı ve ayarlar korundu.'
echo 'Windows ajanı için: C:\ProgramData\Ufuk-FileAudit\uninstall.ps1'
if [[ "${1:-}" == --purge ]]; then
 read -r -p 'Veritabanı dahil tüm kurulum klasörünü silmek için SIL yazın: ' answer < /dev/tty
 if [[ "$answer" == SIL ]]; then cd /;rm -rf -- "$ROOT";fi
fi
