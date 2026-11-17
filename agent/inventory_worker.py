"""Metadata-only local owner/allocated-space inventory; low priority; no ACL changes."""
import os,time,json,uuid,ctypes,logging
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
from logging.handlers import RotatingFileHandler
import requests,win32security,win32process,win32api
from ctypes import wintypes

ROOT=Path(__file__).resolve().parent.parent
CONFIG=json.loads((ROOT/'agent/config.json').read_text(encoding='utf-8'))
BASE=CONFIG['url'].split('/monitor/api/')[0]
HEADERS={'Authorization':'Token '+(CONFIG.get('token') or CONFIG.get('basic-auth'))}
ROOT.joinpath('inventory').mkdir(exist_ok=True)
LOG=logging.getLogger('inventory');LOG.setLevel(logging.INFO)
LOG.addHandler(RotatingFileHandler(ROOT/'logs/inventory.log',maxBytes=2000000,backupCount=3,encoding='utf-8'))
STATE=ROOT/'inventory/state.json';PROGRESS=ROOT/'inventory/progress.json'
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
allocated=kernel.GetCompressedFileSizeW;allocated.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)];allocated.restype=ctypes.c_ulong
class FileStandardInfo(ctypes.Structure):
    _fields_=[('allocation',ctypes.c_longlong),('eof',ctypes.c_longlong),('links',wintypes.DWORD),('delete_pending',ctypes.c_ubyte),('directory',ctypes.c_ubyte)]
kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];kernel.CreateFileW.restype=wintypes.HANDLE
kernel.GetFileInformationByHandleEx.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];kernel.GetFileInformationByHandleEx.restype=wintypes.BOOL
kernel.CloseHandle.argtypes=[wintypes.HANDLE]
def extended(path):return path if path.startswith(chr(92)*2+'?') else chr(92)*2+'?'+chr(92)+path
def now():return datetime.now(timezone.utc).isoformat()
def write(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
def physical(path,attributes):
    path=extended(path)
    if not attributes&(0x800|0x200):
        handle=kernel.CreateFileW(path,0x80,7,None,3,0x00200000,None)
        if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        try:
            info=FileStandardInfo()
            if not kernel.GetFileInformationByHandleEx(handle,1,ctypes.byref(info),ctypes.sizeof(info)):raise ctypes.WinError(ctypes.get_last_error())
            return info.allocation
        finally:kernel.CloseHandle(handle)
    high=ctypes.c_ulong();ctypes.set_last_error(0);low=allocated(path,ctypes.byref(high))
    if low==0xffffffff and ctypes.get_last_error():raise ctypes.WinError(ctypes.get_last_error())
    return (high.value<<32)|low
def scan():
    started=now();folders={};folder_details_complete=True;groups={};cache={};errors=skipped=files=0;links=set();checkpoint=time.monotonic();issues=[]
    def issue(kind,path,exc=None):
        if len(issues)<250:issues.append({'kind':kind,'path':str(path),'error':str(exc)[:300] if exc else '', 'code':getattr(exc,'winerror',None) or getattr(exc,'errno',None)})
    write(PROGRESS,{'state':'running','started_at':started,'files':0,'errors':0})
    for share,root in CONFIG['share_paths'].items():
        dirs=[root]
        while dirs:
            directory=dirs.pop()
            try:
                with os.scandir(extended(directory)) as iterator:
                    for entry in iterator:
                        try:
                            st=entry.stat(follow_symlinks=False)
                            if getattr(st,'st_file_attributes',0)&0x400:skipped+=1;continue
                            if entry.is_dir(follow_symlinks=False):dirs.append(entry.path);continue
                            if not entry.is_file(follow_symlinks=False):continue
                            if st.st_nlink>1:
                                identity=(st.st_dev,st.st_ino)
                                if identity in links:continue
                                links.add(identity)
                            try:
                                sd=win32security.GetNamedSecurityInfo(extended(entry.path),win32security.SE_FILE_OBJECT,win32security.OWNER_SECURITY_INFORMATION)
                                sid=sd.GetSecurityDescriptorOwner();key=win32security.ConvertSidToStringSid(sid)
                                if key not in cache:
                                    try:
                                        name,domain,_=win32security.LookupAccountSid(None,sid);cache[key]=(domain+'\\' if domain else '')+name
                                    except Exception:cache[key]=key
                                owner=cache[key]
                            except Exception as exc:owner='Sahip okunamadı';errors+=1;issue('owner',entry.path,exc)
                            key=(share,owner)
                            row=groups.setdefault(key,{'share':share,'owner':owner,'files':0,'logical_bytes':0,'allocated_bytes':0,'allocation_errors':0})
                            row['files']+=1;row['logical_bytes']+=st.st_size
                            space=0;allocation_failed=0
                            try:
                                space=physical(entry.path,getattr(st,'st_file_attributes',0));row['allocated_bytes']+=space
                            except OSError as exc:row['allocation_errors']+=1;errors+=1;allocation_failed=1;issue('allocation',entry.path,exc)
                            plain=entry.path[4:] if entry.path.startswith(chr(92)*2+'?'+chr(92)) else entry.path
                            relative=os.path.relpath(plain,root).split(os.sep)
                            folder=os.path.join(root,relative[0]) if len(relative)>1 else root
                            fkey=(share,owner,folder)
                            if fkey in folders or len(folders)<10000:
                                item=folders.setdefault(fkey,{'share':share,'owner':owner,'path':folder,'files':0,'logical_bytes':0,'allocated_bytes':0,'allocation_errors':0})
                                item['files']+=1;item['logical_bytes']+=st.st_size;item['allocated_bytes']+=space;item['allocation_errors']+=allocation_failed
                            else:folder_details_complete=False
                            files+=1
                            if files%500==0:time.sleep(.03)
                        except (OSError,ValueError) as exc:errors+=1;issue('entry',entry.path,exc)
                        if time.monotonic()-checkpoint>=10:
                            write(PROGRESS,{'state':'running','started_at':started,'files':files,'errors':errors,'share':share});checkpoint=time.monotonic()
            except OSError as exc:errors+=1;issue('directory',directory,exc)
    result={'scan_id':str(uuid.uuid4()),'started_at':started,'completed_at':now(),'owners':list(groups.values()),'folders':list(folders.values()),'folder_details_complete':folder_details_complete,'errors':errors,'skipped':skipped}
    write(ROOT/'inventory'/('outbox-'+result['scan_id']+'.json'),result)
    write(PROGRESS,{'state':'complete','started_at':started,'completed_at':result['completed_at'],'files':files,'errors':errors,'skipped':skipped})
    write(ROOT/'inventory/issues.json',{'completed_at':result['completed_at'],'errors':errors,'skipped':skipped,'samples':issues,'sample_limit':250})
    LOG.info('Scan completed: files=%s errors=%s skipped=%s',files,errors,skipped)
    return result
def upload():
    for path in sorted(ROOT.joinpath('inventory').glob('outbox-*.json')):
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            clock=datetime.now(timezone.utc)
            try:boundary=clock.replace(year=clock.year-1)
            except ValueError:boundary=clock.replace(year=clock.year-1,day=28)
            if datetime.fromisoformat(data['completed_at'])<boundary:
                path.unlink();LOG.info('Expired queued inventory removed');continue
            response=requests.post(BASE+'/monitor/api/inventory/',json=data,headers=HEADERS,timeout=60)
            if response.status_code in (200,201):path.unlink();LOG.info('Inventory delivered')
            else:LOG.warning('Inventory HTTP %s',response.status_code)
        except Exception as e:LOG.warning('Inventory delivery: %s',type(e).__name__)
def main():
    try:win32process.SetPriorityClass(win32api.GetCurrentProcess(),win32process.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:pass
    state=json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    while True:
        try:
            upload();local=datetime.now();today=local.date().isoformat();request_id=None
            try:
                response=requests.get(BASE+'/monitor/api/scan/',headers=HEADERS,timeout=10)
                if response.ok:request_id=response.json().get('request_id')
            except Exception:pass
            due=not state.get('last_scan') or (local.hour>=3 and state.get('last_scan')!=today)
            if due or request_id:
                if request_id:requests.post(BASE+'/monitor/api/scan/ack/',headers=HEADERS,json={'request_id':request_id},timeout=10).raise_for_status()
                scan();state['last_scan']=today;write(STATE,state);upload()
        except Exception:LOG.exception('Inventory worker cycle failed')
        time.sleep(60)
if __name__=='__main__':main()
