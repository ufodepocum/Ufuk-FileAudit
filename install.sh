#!/usr/bin/env bash
# Ufuk-FileAudit 1.1.1: extracted-source installer and website bootstrap.
set -euo pipefail
VERSION=1.1.1
SOURCE_URL=''
DEST=/opt/ufuk-fileaudit
DOWNLOAD_ONLY=0
PLAN=0
PASS=()
while (($#)); do
 case "$1" in
  --source) SOURCE_URL="${2:?Web klasörü adresi gerekli}";shift 2;;
  --target) DEST="${2:?Hedef klasör gerekli}";shift 2;;
  --download-only) DOWNLOAD_ONLY=1;shift;;
  --plan) PLAN=1;shift;;
  --help|-h) printf '%s\n' 'Ufuk-FileAudit kurulumu' 'sudo bash install.sh [--source https://site/klasor/] [--target /opt/ufuk-fileaudit]' 'bash install.sh --source URL --download-only --target ./kaynak' 'bash install.sh --plan (yerel kaynaktan değişiklik yapmadan akışı gösterir)';exit 0;;
  *) PASS+=("$1");shift;;
 esac
done
if [[ "${EUID:-$(id -u)}" != 0 && "$DOWNLOAD_ONLY" != 1 && "$PLAN" != 1 ]]; then echo 'Kurulumu sudo ile çalıştırın: sudo bash install.sh';exit 1;fi
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || printf '')
if [[ -f "$SCRIPT_DIR/app/manage.py" && -f "$SCRIPT_DIR/installer/wizard.py" ]]; then
 REPO="$SCRIPT_DIR"
else
 if [[ -z "$SOURCE_URL" ]]; then
  read -r -p 'Kurulum dosyalarının bulunduğu web klasörü adresi: ' SOURCE_URL < /dev/tty
 fi
 command -v python3 >/dev/null || { echo 'Önce Python kurun: sudo apt-get update && sudo apt-get install -y python3';exit 1; }
 command -v curl >/dev/null || { echo 'Önce curl kurun: sudo apt-get install -y curl';exit 1; }
 SOURCE_URL="${SOURCE_URL%/}/"
 TEMP=$(mktemp -d)
 trap 'rm -rf -- "$TEMP"' EXIT
 curl --fail --location --retry 2 --proto '=http,https' --proto-redir '=http,https' "$SOURCE_URL/SHA256SUMS" -o "$TEMP/SHA256SUMS"
 ARCHIVE="Ufuk-FileAudit-${VERSION}.tar.gz"
 curl --fail --location --retry 2 --proto '=http,https' --proto-redir '=http,https' "$SOURCE_URL/$ARCHIVE" -o "$TEMP/$ARCHIVE"
 python3 - "$TEMP/$ARCHIVE" "$TEMP/SHA256SUMS" "$DEST" "$ARCHIVE" <<'PY'
import hashlib,sys,tarfile,os,shutil
from pathlib import Path,PurePosixPath
archive,checks,target,name=sys.argv[1:]
expected=[]
for line in Path(checks).read_text().splitlines():
 parts=line.split()
 if len(parts)==2 and parts[1].lstrip('*')==name:expected.append(parts[0].lower())
if len(expected)!=1 or hashlib.sha256(Path(archive).read_bytes()).hexdigest()!=expected[0]:raise SystemExit('SHA256 doğrulaması başarısız; paket açılmadı.')
root=Path(target).expanduser().resolve()
if root.exists() and any(root.iterdir()):raise SystemExit('Hedef klasör boş değil. Farklı --target seçin veya mevcut klasördeki install.sh ile sürdürün.')
root.mkdir(parents=True,exist_ok=True)
with tarfile.open(archive,'r:gz') as tar:
 members=tar.getmembers()
 if len(members)>20000 or sum(m.size for m in members)>512*1024*1024:raise SystemExit('Paket boyutu sınırı aşıldı.')
 for m in members:
  p=PurePosixPath(m.name)
  if p.is_absolute() or '..' in p.parts or m.issym() or m.islnk() or not(m.isdir() or m.isfile()):raise SystemExit('Güvensiz arşiv girdisi.')
  parts=p.parts[1:]
  if not parts:continue
  dest=root.joinpath(*parts).resolve()
  if root not in dest.parents:raise SystemExit('Arşiv hedef dışına çıkıyor.')
  if m.isdir():dest.mkdir(parents=True,exist_ok=True)
  else:
   dest.parent.mkdir(parents=True,exist_ok=True)
   with tar.extractfile(m) as src,open(dest,'wb') as out:shutil.copyfileobj(src,out)
   dest.chmod(0o755 if dest.suffix=='.sh' else 0o644)
if not (root/'installer/wizard.py').is_file():raise SystemExit('Paket içeriği eksik.')
print('Kaynak paketi doğrulandı ve açıldı: '+str(root))
PY
 REPO=$(cd -- "$DEST" && pwd)
fi
if [[ "$DOWNLOAD_ONLY" == 1 ]]; then printf 'Kaynak hazır: %s\n' "$REPO";exit 0;fi
if [[ "$PLAN" == 1 ]]; then exec python3 "$REPO/installer/wizard.py" --plan --root "$DEST" "${PASS[@]}";fi
if [[ "${EUID:-$(id -u)}" != 0 ]]; then echo 'Kurulumu sudo ile çalıştırın: sudo bash install.sh';exit 1;fi
if [[ -z "${BASH_VERSION:-}" ]]; then echo 'Bu betik bash gerektirir.';exit 1;fi
source /etc/os-release
if [[ "$ID" != ubuntu || ! "$VERSION_ID" =~ ^(22\.04|24\.04)$ ]]; then echo 'Desteklenen sürümler: Ubuntu 22.04 LTS ve 24.04 LTS (64 bit).';exit 1;fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl python3 python3-venv
if ! command -v docker >/dev/null; then
 if dpkg-query -W -f='${Status}' containerd 2>/dev/null | grep -q 'install ok installed'; then
  echo 'Mevcut containerd kurulumu var. Docker kurulumunu önceden tamamlayın; mevcut servisler değiştirilmedi.';exit 1
 fi
 install -m 0755 -d /etc/apt/keyrings
 curl -fsSL --proto '=https' https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
 chmod a+r /etc/apt/keyrings/docker.asc
 cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
 apt-get update
 apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
 systemctl enable --now docker
fi
docker info >/dev/null
docker compose version >/dev/null || { echo 'Docker Compose eklentisi eksik. Compose 2.30+ yükleyip tekrar çalıştırın.';exit 1; }
python3 "$REPO/installer/wizard.py" --stage-only --source-root "$REPO" --root "$DEST"
REPO=$(cd -- "$DEST" && pwd)
python3 -m venv "$REPO/.installer-venv"
"$REPO/.installer-venv/bin/python" -m pip install --disable-pip-version-check -r "$REPO/installer/requirements.txt"
exec "$REPO/.installer-venv/bin/python" "$REPO/installer/wizard.py" --root "$REPO" "${PASS[@]}"
