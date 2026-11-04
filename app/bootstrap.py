"""Initialize a new installation once, without resetting existing passwords."""
import os,ipaddress
os.environ.setdefault('DJANGO_SETTINGS_MODULE','AuditSphere.settings')
import django
django.setup()
from django.contrib.auth.models import User
from monitor.models import APIToken
from reports.models import InitialAccount

def initialize():
    server=str(ipaddress.IPv4Address(os.environ['FILESERVER_IP']))
    user,created=User.objects.get_or_create(username='admin',defaults={'is_active':True,'is_staff':True,'is_superuser':True})
    if created:
        user.set_password('admin');user.save()
        InitialAccount.objects.create(user=user,initial_hash=user.password,must_change=True)
    APIToken.objects.get_or_create(client='fileserver-'+server,defaults={'whitelisted_ips':server})
    print('Ufuk-FileAudit ilk kurulum ayarları hazır. Mevcut parolalar korunur.')
if __name__=='__main__':initialize()
