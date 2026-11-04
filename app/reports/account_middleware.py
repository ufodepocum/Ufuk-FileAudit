from django.shortcuts import redirect
from .models import InitialAccount
class InitialPasswordMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        if request.user.is_authenticated and not request.path.startswith(('/static/','/monitor/api/')):
            state=InitialAccount.objects.filter(user=request.user,must_change=True).first()
            if state:
                if state.initial_hash!=request.user.password:
                    state.must_change=False;state.save(update_fields=['must_change'])
                elif request.path not in ('/admin/password_change/','/admin/password_change/done/','/logout/'):
                    return redirect('/admin/password_change/')
        return self.get_response(request)
