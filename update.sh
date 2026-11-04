#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ "${EUID:-$(id -u)}" != 0 ]]; then echo 'sudo bash update.sh ile çalıştırın.';exit 1;fi
mkdir -p "$ROOT/backups"
chmod 700 "$ROOT/backups"
STAMP=$(date +%Y%m%d-%H%M%S)
docker compose --project-directory "$ROOT" exec -T web python -c "import sqlite3;a=sqlite3.connect('/data/db.sqlite3');b=sqlite3.connect('/data/pre-update.sqlite3');a.backup(b);b.close();a.close()"
mv "$ROOT/data/pre-update.sqlite3" "$ROOT/backups/db-$STAMP.sqlite3"
docker compose --project-directory "$ROOT" build
docker compose --project-directory "$ROOT" up -d
echo 'Web uygulaması güncellendi. Ajan değişiklikleri için install.sh sihirbazını tekrar çalıştırın.'
