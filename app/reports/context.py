from django.conf import settings
def product(request):
    from monitor.models import APIToken
    return {'product_name':'Ufuk-FileAudit','registered_servers':APIToken.objects.filter(server_ip__isnull=False).count()}
