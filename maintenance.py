"""Hourly calendar-year retention and seven-day local backup cleanup."""
from pathlib import Path
import subprocess,time
root=Path(__file__).resolve().parent
subprocess.run(['docker','compose','--project-directory',str(root),'exec','-T','web','python','manage.py','purge_audit'],cwd=root,check=True)
threshold=time.time()-7*86400
for file in root.joinpath('backups').glob('*'):
    if file.is_file() and file.stat().st_mtime<threshold:file.unlink()
