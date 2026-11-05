import json,os
from django.conf import settings
from django.db import migrations

def register(apps,schema_editor):
    Token=apps.get_model('monitor','APIToken');Log=apps.get_model('monitor','LogEntry')
    Snapshot=apps.get_model('reports','InventorySnapshot');Scan=apps.get_model('reports','ScanRequest')
    ip=settings.FILESERVER_IP
    if not ip:return
    token=Token.objects.filter(client='fileserver-'+ip).first() or Token.objects.filter(whitelisted_ips=ip).first()
    if not token:return
    token.server_ip=ip
    token.share_paths=json.loads(os.environ.get('AUDIT_SHARE_PATHS_JSON','{}')) or dict.fromkeys(settings.AUDIT_SHARES,'')
    token.save(update_fields=['server_ip','share_paths'])
    Log.objects.filter(source__isnull=True).update(source=token)
    Snapshot.objects.filter(source__isnull=True,host=ip).update(source=token)
    Scan.objects.filter(source__isnull=True).update(source=token)

class Migration(migrations.Migration):
    dependencies=[('reports','0003_inventorysnapshot_source_scanrequest_source')]
    operations=[migrations.RunPython(register,migrations.RunPython.noop)]
