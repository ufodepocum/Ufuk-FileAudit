"""Initialize a new installation once, without resetting existing passwords."""
import os,ipaddress,json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','AuditSphere.settings')
import django
django.setup()
from django.contrib.auth.models import User
from monitor.models import APIToken
from reports.models import InitialAccount
from django.conf import settings

def initialize():
    server=str(ipaddress.IPv4Address(os.environ['FILESERVER_IP']))
    if not User.objects.filter(is_active=True,is_superuser=True).exists():
        user,created=User.objects.get_or_create(username='admin',defaults={'is_active':True,'is_staff':True,'is_superuser':True})
        if created:
            user.set_password('admin');user.save()
            InitialAccount.objects.create(user=user,initial_hash=user.password,must_change=True)
    client=APIToken.objects.filter(server_ip=server).first()
    if not client:client,_=APIToken.objects.get_or_create(client='fileserver-'+server,defaults={'whitelisted_ips':server,'server_ip':server})
    # Populate only legacy empty fields; panel-managed choices survive container restarts.
    if not client.server_ip and not APIToken.objects.filter(server_ip=server).exclude(pk=client.pk).exists():
        client.server_ip=server
        if not client.share_paths:client.share_paths=json.loads(os.environ.get('AUDIT_SHARE_PATHS_JSON','{}')) or dict.fromkeys(settings.AUDIT_SHARES,'')
        client.save()
    elif not client.share_paths and not client.installed_at:
        client.share_paths=json.loads(os.environ.get('AUDIT_SHARE_PATHS_JSON','{}')) or dict.fromkeys(settings.AUDIT_SHARES,'');client.save(update_fields=['share_paths'])
    print('Ufuk-FileAudit ilk kurulum ayarları hazır. Mevcut parolalar korunur.')
if __name__=='__main__':initialize()
