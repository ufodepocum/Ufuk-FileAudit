from pathlib import Path
import os,subprocess,sys,time,logging
from logging.handlers import RotatingFileHandler
root=Path(__file__).resolve().parent.parent
os.chdir(root/'agent')
log=logging.getLogger('launcher');log.setLevel(logging.INFO)
log.addHandler(RotatingFileHandler(root/'logs/launcher.log',maxBytes=2000000,backupCount=3))
if not Path(r'C:\Windows\System32\Npcap\wpcap.dll').exists() and not Path(r'C:\Windows\System32\wpcap.dll').exists():
    (root/'status.txt').write_text('WAITING: Npcap driver installation required. No file activity is being collected.')
    log.warning('Npcap missing; capture not started.');sys.exit(0)
(root/'status.txt').write_text('STARTING: capture requested; verify capture-error.log and real file events.')
with open(root/'logs/agent-console.log','w',encoding='utf-8') as out:
    p=subprocess.Popen([sys.executable,'-u','agent.py','-c','config.json'],stdout=out,stderr=out)
    rc=p.wait()
(root/'status.txt').write_text('STOPPED: agent exited, code '+str(rc))
sys.exit(rc or 1)
