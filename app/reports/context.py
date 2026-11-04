from django.conf import settings
def product(request):
    return {'product_name':'Ufuk-FileAudit','fileserver_ip':settings.FILESERVER_IP,'audit_shares':settings.AUDIT_SHARES}
