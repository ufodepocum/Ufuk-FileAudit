#!/usr/bin/env python3
"""Interactive installation. Administrator passwords live only in process memory."""
import argparse,getpass,ipaddress,json,os,secrets,shutil,socket,subprocess,sys,time,uuid,re
from pathlib import Path
from urllib.request import urlopen

VERSION='1.1.1'
WINDOWS_ROOT=r'C:\ProgramData\Ufuk-FileAudit'
class SetupError(RuntimeError):pass

def ipv4(value):
    try:
        address=ipaddress.IPv4Address(value)
        if address.is_unspecified or address.is_loopback or address.is_multicast:raise ValueError()
        return str(address)
    except ValueError:raise SetupError('Geçerli bir IPv4 adresi girin.')
def ask(label,default=None):
    value=input(label+(f' [{default}]' if default is not None else '')+': ').strip()
    return value or default or ''
def yes(label):return ask(label+' (e/H)','H').casefold() in ('e','evet','y','yes')
def prompt_ip(label,default=None):
    while True:
        try:return ipv4(ask(label,default))
        except SetupError as e:print(e)
def choose_shares(text,available):
    wanted=[x.strip() for x in text.split(',') if x.strip()]
    lookup={x['Name'].casefold():x for x in available}
    if not wanted:raise SetupError('En az bir paylaşım seçilmeli.')
    if len({x.casefold() for x in wanted})!=len(wanted):raise SetupError('Aynı paylaşımı birden çok kez seçmeyin.')
    result={}
    for name in wanted:
        if name.casefold() not in lookup:raise SetupError('Paylaşım bulunamadı: '+name)
        row=lookup[name.casefold()];result[row['Name']]=row['Path']
    return result
def run_command(args,**kwargs):
    result=subprocess.run(args,check=True,**kwargs)
    return result
def write_private(path,text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as out:out.write(text)
    path.chmod(0o600)

def stage(source,target):
    source=Path(source).resolve();target=Path(target).resolve()
    if not (source/'app/manage.py').is_file() or not (source/'installer/wizard.py').is_file():raise SetupError('Kaynak paketi eksik.')
    if target==Path(target.anchor):raise SetupError('Kök dizin kurulum hedefi olamaz.')
    if source==target:return target
    if source in target.parents:raise SetupError('Hedefi kaynak klasörünün içine yerleştirmeyin.')
    if target.exists() and any(target.iterdir()) and not (target/'installation.json').exists():raise SetupError('Hedef klasör boş değil ve tanınan bir kurulum değil.')
    target.mkdir(parents=True,exist_ok=True);target.chmod(0o700)
    for entry in source.iterdir():
        if entry.name in ('.git','.env','runtime.env','.installer-venv','data','backups','__pycache__','installation.json'):continue
        dest=target/entry.name
        if entry.is_symlink():raise SetupError('Kaynakta sembolik bağlantı desteklenmiyor.')
        if entry.is_dir():shutil.copytree(entry,dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:shutil.copyfile(entry,dest)
    return target

def wait_for_npcap(remote,script,confirm=input):
    while True:
        result=remote.run(script)
        if result.strip()=='READY':print('  Npcap servisi ve sürücü dosyaları doğrulandı.');return
        if result.strip()!='INSTALL_REQUIRED':raise SetupError('Npcap kontrolü beklenmeyen bir yanıt verdi.')
        print('\n  Npcap eksik. Windows sunucusuna RDP ile bağlanın ve şu imzalı dosyayı açın:')
        print('  '+WINDOWS_ROOT+r'\downloads\npcap-1.90.exe')
        print('  Ücretsiz Npcap grafik kurulum ister. Ubuntu üzerinde Npcap kurulmaz.')
        value=confirm('  Windows kurulumu bittiğinde Enter; çıkmak için q: ').strip()
        if value.casefold()=='q':raise SetupError('Npcap adımı tamamlanmadı. Kurucuyu tekrar çalıştırarak sürdürebilirsiniz.')

def compose(root,*args,capture=False):
    result=run_command(['docker','compose','--project-directory',str(root),*args],cwd=root,text=True,capture_output=capture)
    return result.stdout.strip() if capture else ''

def configure_server(root,server_ip,web_ip,port,share_paths):
    env=root/'runtime.env';existing={}
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            key,sep,value=line.partition('=')
            if sep:existing[key]=value
        if existing.get('FILESERVER_IP') not in (None,server_ip):raise SetupError('Bu kurulum başka bir dosya sunucusuna bağlı. Yeni bir kurulum klasörü kullanın.')
    secret=existing.get('DJANGO_SECRET_KEY') or secrets.token_urlsafe(48)
    write_private(root/'.env',f'WEB_BIND_IP={web_ip}\nWEB_PORT={port}\n')
    write_private(env,'\n'.join(['DJANGO_SECRET_KEY='+secret,'FILESERVER_IP='+server_ip,'AUDIT_SHARES_JSON='+json.dumps(list(share_paths),ensure_ascii=False),'AUDIT_SHARE_PATHS_JSON='+json.dumps(share_paths,ensure_ascii=False),'WEB_ALLOWED_HOSTS=localhost,127.0.0.1,'+web_ip])+'\n')
    data=root/'data';data.mkdir(exist_ok=True)
    if os.name!='nt':os.chown(data,10001,10001)
    data.chmod(0o750)
    write_private(root/'installation.json',json.dumps({'product':'Ufuk-FileAudit','version':VERSION,'server_ip':server_ip,'web_ip':web_ip,'port':port,'shares':list(share_paths)},ensure_ascii=False,indent=2))

def install_timer(root):
    service='[Unit]\nDescription=Ufuk-FileAudit bir yillik kayit temizligi\nAfter=docker.service\nRequires=docker.service\n[Service]\nType=oneshot\nExecStart=/usr/bin/python3 "'+str(root/'maintenance.py')+'"\n'
    timer='[Unit]\nDescription=Ufuk-FileAudit saatlik log temizligi\n[Timer]\nOnCalendar=hourly\nPersistent=true\n[Install]\nWantedBy=timers.target\n'
    Path('/etc/systemd/system/ufuk-fileaudit-retention.service').write_text(service)
    Path('/etc/systemd/system/ufuk-fileaudit-retention.timer').write_text(timer)
    run_command(['systemctl','daemon-reload'])
    run_command(['systemctl','enable','--now','ufuk-fileaudit-retention.timer'])

def read_token(root,server_ip):
    program="import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','AuditSphere.settings');django.setup();from monitor.models import APIToken;print(APIToken.objects.get(server_ip=os.environ['FILESERVER_IP']).token)"
    value=compose(root,'exec','-T','web','python','-c',program,capture=True)
    return str(uuid.UUID(value.splitlines()[-1]))

def check_docker(root,web_ip,port):
    version=run_command(['docker','compose','version','--short'],capture_output=True,text=True).stdout
    match=re.search(r'(\d+)\.(\d+)',version)
    if not match or tuple(map(int,match.groups()))<(2,30):raise SetupError('Docker Compose 2.30 veya daha yeni sürümü gerekli.')
    projects=run_command(['docker','ps','-a','--filter','label=com.docker.compose.project=ufuk-fileaudit','--format','{{.Label "com.docker.compose.project.working_dir"}}'],capture_output=True,text=True).stdout
    paths={Path(x.strip()).resolve() for x in projects.splitlines() if x.strip()}
    if paths and paths!={root.resolve()}:raise SetupError('Bu Ubuntu üzerinde başka klasörde Ufuk-FileAudit var; mevcut kurulum değiştirilmedi.')
    if not paths:
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:sock.bind((web_ip,port))
        except OSError:raise SetupError('Ubuntu IP adresi bu makinede bulunmuyor veya seçilen port kullanılıyor.')

def wait_web(url):
    for _ in range(60):
        try:
            with urlopen(url+'/login/',timeout=3) as response:
                if response.status==200:return
        except Exception:pass
        time.sleep(1)
    raise SetupError('Web arayüzü başlamadı. docker compose logs komutuyla sunucu loglarını inceleyin.')

def suggested_ip(server_ip):
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.connect((server_ip,445));return sock.getsockname()[0]
    except OSError:return ''

def perform(root,check_only=False):
    try:from .remote import WindowsRemote
    except ImportError:from remote import WindowsRemote
    previous=json.loads((root/'installation.json').read_text()) if (root/'installation.json').exists() else {}
    print('\nUfuk-FileAudit '+VERSION+' kurulum sihirbazı\n')
    server_ip=prompt_ip('1/7 Dosya sunucusunun IP adresi',previous.get('server_ip'))
    username=ask('Domain veya yerel yönetici hesabı (DOMAIN\\kullanıcı veya SUNUCU\\kullanıcı)')
    if '\\' not in username or not username.split('\\',1)[1]:raise SetupError('Hesabı DOMAIN\\kullanıcı ya da SUNUCU\\kullanıcı biçiminde yazın.')
    password=getpass.getpass('Yönetici parolası (kaydedilmez): ')
    if not password:raise SetupError('Boş parola ile devam edilemez.')
    remote=WindowsRemote(server_ip,username,password)
    scripts=root/'installer/windows'
    config={'server_ip':server_ip}
    try:details=json.loads(remote.run((scripts/'preflight.ps1').read_text(encoding='utf-8'),config))
    except Exception as e:raise SetupError('Windows yönetim bağlantısı kurulamadı. WinRM 5985 erişimini ve yönetici hesabını kontrol edin. '+type(e).__name__)
    print('  Bağlantı başarılı: '+details['computer']+' / '+details['os'])
    if check_only:
        print('  Npcap: '+('hazır' if details['npcap'] else 'kurulum gerekli'))
        print('  Paylaşımlar: '+', '.join(x['Name'] for x in details['shares']));return
    migrate=bool(details.get('tasks'))
    if migrate and not yes('Bu sunucuda Ufuk-FileAudit ajanı var. Bu kurulumun Ubuntu adresine taşınsın mı?'):
        raise SetupError('Mevcut ajan değiştirilmedi.')
    print('\n2/7 İzlenecek paylaşımları seçin:')
    for row in details['shares']:print('  '+row['Name']+'  →  '+row['Path'])
    while True:
        try:
            selected=choose_shares(ask('Paylaşım adları (virgülle ayırın)',','.join(previous.get('shares',[])) or None),details['shares']);break
        except SetupError as e:print(e)
    aliases=list(dict.fromkeys(x['InterfaceAlias'] for x in details['interfaces']))
    if len(aliases)!=1:raise SetupError('Yazılan IP için tek bir ağ arabirimi bulunamadı. Dosya sunucusunun gerçek yerel IPv4 adresini kullanın.')
    web_ip=prompt_ip('Ubuntu arayüz IP adresi (Windows sunucusu erişebilmeli)',previous.get('web_ip') or suggested_ip(server_ip))
    try:port=int(ask('Web arayüzü portu',str(previous.get('port',8085))))
    except ValueError:raise SetupError('Port sayısal olmalı.')
    if not 1<=port<=65535:raise SetupError('Port 1-65535 aralığında olmalı.')
    check_docker(root,web_ip,port)
    print('\n3/7 Windows Npcap denetimi')
    wait_for_npcap(remote,(scripts/'npcap.ps1').read_text(encoding='utf-8'))
    print('\n4/7 Ubuntu web uygulaması kuruluyor')
    configure_server(root,server_ip,web_ip,port,selected)
    compose(root,'build');compose(root,'up','-d')
    url=f'http://{web_ip}:{port}';wait_web(url)
    token=read_token(root,server_ip)
    install_timer(root)
    print('  Web arayüzü ve bir yıllık log temizleme görevi hazır.')
    print('\n5/7 Windows Python ve Wireshark bileşenleri hazırlanıyor')
    remote.put_files({WINDOWS_ROOT+r'\downloads\agent-requirements.txt':(root/'agent/requirements.txt').read_bytes()})
    remote.run((scripts/'dependencies.ps1').read_text(encoding='utf-8'))
    print('\n6/7 Ajan dosyaları ve SYSTEM görevleri kuruluyor')
    agent_config={'server_ip':server_ip,'interface':aliases[0],'url':url+'/monitor/api/log/','token':token,'shares':list(selected),'share_paths':selected,'save_to_file':False,'num_files':7,'logs_directory':WINDOWS_ROOT+r'\logs','pcap_files':WINDOWS_ROOT+r'\unused.pcapng'}
    files={WINDOWS_ROOT+'\\stage\\agent\\'+f.name:f.read_bytes() for f in (root/'agent').glob('*.py')}
    files[WINDOWS_ROOT+r'\stage\agent\config.json']=json.dumps(agent_config,ensure_ascii=False,indent=2)
    files[WINDOWS_ROOT+r'\stage\uninstall.ps1']=(root/'agent/uninstall.ps1').read_bytes()
    remote.put_files(files)
    remote.run((scripts/'validate-agent.ps1').read_text(encoding='utf-8'))
    activation=json.loads(remote.run((scripts/'activate.ps1').read_text(encoding='utf-8'),{'migrate':migrate,'api_url':url}))
    print('\n7/7 API, Npcap ve paket yakalama doğrulanıyor')
    try:
        result=json.loads(remote.run((scripts/'verify.ps1').read_text(encoding='utf-8')))
        if result.get('api_status')!=201 or result.get('capture')!='Running':raise SetupError('Ajan doğrulaması başarısız.')
    except Exception:
        remote.run((scripts/'rollback.ps1').read_text(encoding='utf-8'),{'backup':activation['backup']})
        raise SetupError('Yeni ajan doğrulanamadı; önceki Windows görevleri geri yüklendi. Ubuntu web arayüzü korunuyor.')
    program="import os,json,django,sys;os.environ.setdefault('DJANGO_SETTINGS_MODULE','AuditSphere.settings');django.setup();from monitor.models import APIToken;from django.utils import timezone;APIToken.objects.filter(server_ip=os.environ['FILESERVER_IP']).update(share_paths=json.loads(sys.argv[1]),computer_name=sys.argv[2],installed_at=timezone.now(),setup_error='')"
    compose(root,'exec','-T','web','python','-c',program,json.dumps(selected,ensure_ascii=False),details['computer'])
    print('\nKurulum tamamlandı.\nArayüz: '+url+'\nYeni kurulumda ilk hesap: admin / admin; ilk girişte parolanızı değiştirin. Mevcut hesaplar ve parolalar korunur.\nDisk sahipliği ölçümü arka planda hazırlanır; sonraki ölçümler her gün 03:00’te yapılır.\nYönetici parolası kaydedilmedi; ajanlar SYSTEM hesabıyla çalışır.')

def main(argv=None):
    parser=argparse.ArgumentParser(description='Ufuk-FileAudit etkileşimli kurulumu')
    parser.add_argument('--root',type=Path,default=Path('/opt/ufuk-fileaudit'))
    parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--stage-only',action='store_true');parser.add_argument('--plan',action='store_true');parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    if args.plan:
        print('1. Dosya sunucusu IP ve yönetici hesabı (parola bellekte)\n2. Gerçek SMB paylaşımlarının seçimi\n3. Windows Npcap kontrolü; gerekirse kullanıcı kurulumunu bekleme\n4. Ubuntu Docker web uygulaması ve ilk admin/admin hesabı\n5. Windows Python/Wireshark\n6. SYSTEM ajan ve envanter görevleri\n7. API/Npcap/yakalama doğrulaması\nKurulum hedefi: '+str(args.root));return 0
    if os.name!='posix' or os.geteuid()!=0:raise SetupError('Bu kurulum Ubuntu üzerinde sudo/root yetkisiyle çalıştırılmalı.')
    root=stage(args.source_root,args.root)
    if args.stage_only:print('Kaynak hazır: '+str(root));return 0
    perform(root,args.check);return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (SetupError,KeyboardInterrupt,EOFError) as exc:print('\nKurulum tamamlanmadı: '+str(exc),file=sys.stderr);sys.exit(1)
    except subprocess.CalledProcessError as exc:print('\nKomut başarısız: '+str(exc.cmd[0])+'. Aynı kurucuyu tekrar çalıştırabilirsiniz.',file=sys.stderr);sys.exit(1)
