"""Staff-only Windows discovery and deployment. Credentials are request-local."""
import json,uuid,sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters,sensitive_variables
from django.views.decorators.http import require_POST
from .models import APIToken

class SetupValidation(ValueError):pass

STAFF=user_passes_test(lambda u:u.is_active and u.is_staff)
ROOT=Path(settings.BASE_DIR).parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
WINDOWS_ROOT=r'C:\ProgramData\Ufuk-FileAudit'

class ServerForm(forms.ModelForm):
    server_ip=forms.GenericIPAddressField(label='Dosya sunucusu IPv4 adresi',protocol='IPv4')
    class Meta:
        model=APIToken
        fields=['client','server_ip']
        labels={'client':'Sunucu adı'}
    def clean_server_ip(self):
        import ipaddress
        value=self.cleaned_data['server_ip'];ip=ipaddress.ip_address(value)
        if ip.is_unspecified or ip.is_loopback or ip.is_multicast or ip.is_link_local:
            raise forms.ValidationError('Sunucunun erişilebilir yerel IPv4 adresini girin.')
        if self.instance.pk and self.instance.installed_at and self.instance.server_ip!=value:
            raise forms.ValidationError('Kurulu sunucunun IP adresi bu formdan değiştirilemez. Yeni sunucu kaydı oluşturun.')
        return value
    def save(self,commit=True):
        obj=super().save(commit=False);obj.whitelisted_ips=obj.server_ip
        if commit:obj.save()
        return obj

@STAFF
def servers(request):
    form=ServerForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        server=form.save()
        messages.success(request,'Sunucu kaydı oluşturuldu. Paylaşımları bulup ajanı kurmak için bağlantıyı tamamlayın.')
        return redirect('monitor:edit_client',token_id=server.pk)
    return render(request,'monitor/manage_clients.html',{'clients':APIToken.objects.order_by('client'),'form':form,'section':'servers'})

@STAFF
def server_detail(request,token_id):
    server=get_object_or_404(APIToken,pk=token_id)
    form=ServerForm(request.POST or None,instance=server)
    if request.method=='POST' and form.is_valid():
        form.save();messages.success(request,'Sunucu bilgileri kaydedildi. Paylaşım seçimi aşağıdaki bağlantı adımlarından yapılır.')
        return redirect('monitor:edit_client',token_id=server.pk)
    return render(request,'monitor/edit_client.html',{'server':server,'form':form,'section':'servers','panel_url':request.build_absolute_uri('/').rstrip('/')})

def script(name):return (ROOT/'installer/windows'/name).read_text(encoding='utf-8')

def inspect(remote,server):
    details=json.loads(remote.run(script('preflight.ps1'),{'server_ip':server.server_ip}))
    aliases=list(dict.fromkeys(row['InterfaceAlias'] for row in details['interfaces']))
    if len(aliases)!=1:raise SetupValidation('Sunucu IP adresi Windows üzerinde tek bir ağ arabirimine karşılık gelmeli.')
    return details,aliases[0]

@sensitive_variables('password','remote','config','files')
@sensitive_post_parameters('password')
@require_POST
@STAFF
def server_action(request,token_id):
    server=get_object_or_404(APIToken,pk=token_id)
    if not server.is_active:return JsonResponse({'error':'Önce bu sunucunun bağlantısını etkinleştirin.'},status=400)
    if not server.server_ip:return JsonResponse({'error':'Önce sunucu IPv4 adresini kaydedin.'},status=400)
    action=request.POST.get('action')
    if action not in ('inspect','npcap','dependencies','deploy'):return JsonResponse({'error':'Geçersiz adım.'},status=400)
    username=request.POST.get('username','').strip();password=request.POST.get('password','')
    if '\\' not in username or not password:return JsonResponse({'error':'DOMAIN\\kullanıcı veya SUNUCU\\kullanıcı ve yönetici parolası gerekli.'},status=400)
    stamp=timezone.now()
    claimed=APIToken.objects.filter(pk=server.pk).filter(Q(setup_started__isnull=True)|Q(setup_started__lt=stamp-timedelta(minutes=30))).update(setup_started=stamp)
    if not claimed:return JsonResponse({'error':'Bu sunucuda başka bir işlem sürüyor. Tamamlanmasını bekleyin.'},status=409)
    try:
        from installer.remote import WindowsRemote
        remote=WindowsRemote(server.server_ip,username,password)
        details,interface=inspect(remote,server)
        if action=='inspect':
            APIToken.objects.filter(pk=server.pk).update(computer_name=details['computer'])
            return JsonResponse({'details':details,'selected':list(server.share_paths)})
        if action=='npcap':
            result=remote.run(script('npcap.ps1'))
            if result not in ('READY','INSTALL_REQUIRED'):raise SetupValidation('Npcap kontrolü tamamlanamadı.')
            return JsonResponse({'ready':result=='READY','message':'Npcap hazır.' if result=='READY' else r'Windows sunucusuna RDP ile bağlanın; C:\ProgramData\Ufuk-FileAudit\downloads\npcap-1.90.exe dosyasını açıp kurulumu tamamlayın. Sonra Npcap kontrolünü tekrar çalıştırın.'})
        if not details['npcap']:raise SetupValidation('Önce Npcap adımını tamamlayıp tekrar kontrol edin.')
        # Creates protected staging directories even when Npcap was installed separately.
        if remote.run(script('npcap.ps1'))!='READY':raise SetupValidation('Npcap hazır değil.')
        if action=='dependencies':
            remote.put_files({WINDOWS_ROOT+r'\downloads\agent-requirements.txt':(ROOT/'agent/requirements.txt').read_bytes()})
            remote.run(script('dependencies.ps1'))
            return JsonResponse({'message':'Python ve Wireshark bileşenleri hazır. Seçtiğiniz paylaşımları kaydedip ajanı kurabilirsiniz.'})
        selected=request.POST.getlist('shares')
        available={row['Name']:row['Path'] for row in details['shares']}
        if not selected or len(selected)!=len(set(selected)) or any(name not in available for name in selected):
            raise SetupValidation('Sunucudan bulunan en az bir gerçek paylaşımı seçin; liste değiştiyse yeniden keşfedin.')
        if details['tasks'] and request.POST.get('replace')!='yes':raise SetupValidation('Mevcut ajan görevlerini güncelleme onayı gerekli.')
        url=request.POST.get('panel_url','').strip().rstrip('/');parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
            raise SetupValidation('Windows sunucusunun erişebildiği panel adresini http(s)://adres:port biçiminde girin.')
        paths={name:available[name] for name in selected}
        config={'server_ip':server.server_ip,'interface':interface,'url':url+'/monitor/api/log/','token':str(server.token),'shares':selected,'share_paths':paths,'save_to_file':False,'num_files':7,'logs_directory':WINDOWS_ROOT+r'\logs','pcap_files':WINDOWS_ROOT+r'\unused.pcapng'}
        files={WINDOWS_ROOT+'\\stage\\agent\\'+p.name:p.read_bytes() for p in (ROOT/'agent').glob('*.py')}
        files[WINDOWS_ROOT+r'\stage\agent\config.json']=json.dumps(config,ensure_ascii=False)
        files[WINDOWS_ROOT+r'\stage\uninstall.ps1']=(ROOT/'agent/uninstall.ps1').read_bytes()
        remote.put_files(files)
        # Allow the newly installed agent to upload its initial inventory while verification runs.
        previous=server.share_paths
        APIToken.objects.filter(pk=server.pk).update(share_paths=paths)
        backup=WINDOWS_ROOT+'\\backups\\panel-'+uuid.uuid4().hex
        try:
            remote.run(script('activate.ps1'),{'migrate':bool(details['tasks']),'api_url':url,'backup':backup})
            result=json.loads(remote.run(script('verify.ps1')))
            if result.get('api_status')!=201 or result.get('capture')!='Running':raise SetupValidation('API veya paket yakalama doğrulanamadı.')
        except Exception:
            APIToken.objects.filter(pk=server.pk).update(share_paths=previous)
            try:remote.run(script('rollback.ps1'),{'backup':backup})
            except Exception:raise SetupValidation('Kurulum doğrulanamadı; geri alma da tamamlanamadı. Windows görevlerini kontrol edin.') from None
            raise SetupValidation('Kurulum doğrulanamadı; önceki ajan ayarları ve görevleri geri yüklendi.') from None
        APIToken.objects.filter(pk=server.pk).update(share_paths=paths,computer_name=details['computer'],installed_at=timezone.now(),setup_error='')
        return JsonResponse({'message':'Ajan ve API doğrulandı. İzlenen paylaşımlar kaydedildi. Disk ölçümü arka planda hazırlanıyor.','reload':True})
    except SetupValidation as error:
        # Only locally generated messages are exposed. Remote exceptions may contain sensitive output.
        return JsonResponse({'error':str(error)},status=400)
    except Exception:
        APIToken.objects.filter(pk=server.pk).update(setup_error='Windows adımı tamamlanamadı. WinRM, yönetici hesabı ve Windows kurulum loglarını kontrol edin.')
        return JsonResponse({'error':'Windows adımı tamamlanamadı. WinRM 5985 erişimini, yönetici hesabını ve C:\\ProgramData\\Ufuk-FileAudit\\logs klasörünü kontrol edin. Bu adımdan tekrar deneyebilirsiniz.'},status=400)
    finally:
        APIToken.objects.filter(pk=server.pk,setup_started=stamp).update(setup_started=None)
