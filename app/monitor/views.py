from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import LogEntry, APIToken
from .serializers import LogEntrySerializer
import uuid
import datetime
import hashlib,json

def save_events(serializer,source=None):
    many=isinstance(serializer.validated_data,list)
    rows=serializer.validated_data if many else [serializer.validated_data]
    objects=[]
    fields=[f.name for f in LogEntry._meta.fields if f.name not in ('id','event_key','source')]
    for row in rows:
        normalized={key:row.get(key) for key in fields}
        normalized['source']=source.pk if source else None
        normalized['when']=row['when'].astimezone(datetime.timezone.utc).isoformat(timespec='microseconds')
        digest=hashlib.sha256(json.dumps(normalized,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        obj,_=LogEntry.objects.get_or_create(event_key=digest,defaults={**row,'source':source})
        objects.append(obj)
    serializer.instance=objects if many else objects[0]
    return objects


class LogEntryList(APIView):
    def post(self, request, format=None):
        data = request.data
        from reports.retention import purge
        from django.core.cache import cache
        if cache.add('ufuk-retention', True, 300):
            purge()
        if isinstance(data, list):  # Check if incoming data is a list
            serializer = LogEntrySerializer(data=data, many=True)  # Set many=True for batch processing
            if serializer.is_valid():
                save_events(serializer,request._request.audit_client)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Handle single log entry case (optional, based on your requirements)
            serializer = LogEntrySerializer(data=data)
            if serializer.is_valid():
                save_events(serializer,request._request.audit_client)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@user_passes_test(lambda u: u.is_active and u.is_staff)
def manage_clients(request):
    if request.method == 'POST':
        client_name = request.POST.get('client_name')
        whitelisted_ips = request.POST.get('whitelisted_ips', '')
        client, created = APIToken.objects.get_or_create(client=client_name)

        # Update the whitelisted IPs if the client already exists or is newly created
        client.whitelisted_ips = whitelisted_ips
        client.save()

        if created:
            messages.success(request, f'Erişim anahtarı oluşturuldu: {client_name}.')
        else:
            messages.info(request, f'İstemci {client_name} güncellendi.')

        return redirect('monitor:clients')

    clients = APIToken.objects.all()
    return render(request, 'monitor/manage_clients.html', {'clients': clients})

@user_passes_test(lambda u: u.is_active and u.is_staff)
@require_POST
def disable_client(request, token_id):
    api_token = get_object_or_404(APIToken, id=token_id)
    api_token.is_active = False
    api_token.save()
    return redirect('monitor:clients')

@user_passes_test(lambda u: u.is_active and u.is_staff)
@require_POST
def enable_client(request, token_id):
    api_token = get_object_or_404(APIToken, id=token_id)
    api_token.is_active = True
    api_token.save()
    return redirect('monitor:clients')

@user_passes_test(lambda u: u.is_active and u.is_staff)
@require_POST
def delete_client(request, token_id):
    api_token = get_object_or_404(APIToken, id=token_id)
    api_token.delete()
    return redirect('monitor:clients')

@user_passes_test(lambda u: u.is_active and u.is_staff)
def edit_client(request, token_id):
    api_token = get_object_or_404(APIToken, id=token_id)

    if request.method == 'POST':
        client_name = request.POST.get('client_name')
        whitelisted_ips = request.POST.get('whitelisted_ips', '')
        api_token.client = client_name
        api_token.whitelisted_ips = whitelisted_ips
        api_token.save()
        messages.success(request, f'İstemci {client_name} ayrıntıları güncellendi.')
        return redirect('monitor:clients')

    return render(request, 'monitor/edit_client.html', {'api_token': api_token})
