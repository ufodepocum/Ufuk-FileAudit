from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import APIToken
class TokenAuthenticationMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        if request.path.startswith('/monitor/api/'):
            header=request.headers.get('Authorization','')
            scheme,_,token=header.partition(' ')
            if scheme!='Token' or not token:
                return JsonResponse({'detail':'Token required'},status=401)
            try:
                api_token=APIToken.objects.get(token=token,is_active=True)
            except (APIToken.DoesNotExist,ValueError,ValidationError):
                return JsonResponse({'detail':'Invalid or inactive token'},status=401)
            if not api_token.is_ip_whitelisted(request.META.get('REMOTE_ADDR','')):
                return JsonResponse({'detail':'IP address not whitelisted'},status=403)
            api_token.last_activity=timezone.now()
            api_token.save(update_fields=['last_activity'])
        return self.get_response(request)
