#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
docker compose --project-directory "$ROOT" ps
docker compose --project-directory "$ROOT" exec -T web python manage.py check
systemctl list-timers ufuk-fileaudit-retention.timer --no-pager
