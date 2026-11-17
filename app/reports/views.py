import csv,json,uuid,base64,gzip,io,binascii
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.decorators import login_required,user_passes_test
from django.db import transaction
from django.db.models import Count,Sum,Q,Max
from django.db.models.functions import TruncDate
from django.http import HttpResponse,JsonResponse
from django.shortcuts import render,redirect
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import InventorySnapshot,OwnerUsage,ScanRequest,FolderUsage
from .forms import Filters,ACTIONS
from .retention import cutoff,purge
from monitor.models import LogEntry,APIToken

def filtered(request):
    form=Filters(request.GET if request.GET else None)
    if not form.is_bound:form=Filters({})
    valid=form.is_valid();data=form.cleaned_data
    qs=LogEntry.objects.filter(when__gte=cutoff())
    if not valid:return form,qs.none()
    qs=qs.filter(when__gte=data['start_date_parsed'],when__lte=data['end_date_parsed'])
    if data.get('server'):qs=qs.filter(source_id=data['server'])
    for field in ['who','host']:
        if data.get(field):qs=qs.filter(**{field+'__icontains':data[field]})
    if data.get('share_name'):qs=qs.filter(Q(share_name__iexact=data['share_name'])|Q(share_name__iendswith='\\'+data['share_name']))
    if data.get('action'):qs=qs.filter(action=data['action'])
    if data.get('search'):
        term=data['search'];qs=qs.filter(Q(what__icontains=term)|Q(old_path__icontains=term)|Q(new_path__icontains=term))
    return form,qs

def base_context(request,form):
    now=timezone.localtime()
    values=request.GET.copy();values.pop('page',None);values.pop('export',None)
    defaults={'start_date':now.replace(hour=0,minute=0,second=0,microsecond=0).strftime('%Y-%m-%dT%H:%M'),'end_date':now.strftime('%Y-%m-%dT%H:%M')}
    # Keep canonical defaults in links and controls for repeatable exports.
    for key,value in defaults.items():
        if not values.get(key):values[key]=value
    display_values=values.copy()
    for key in ['start_date','end_date']:
        try:
            parsed=parse_datetime(values[key])
            if parsed:
                if timezone.is_naive(parsed):parsed=timezone.make_aware(parsed)
                display_values[key]=timezone.localtime(parsed).strftime('%d.%m.%Y %H:%M')
        except (ValueError,TypeError):pass
    display=Filters(display_values)
    return {'filter_form':display,'query':values.urlencode(),'min_date':timezone.localtime(cutoff()).strftime('%Y-%m-%dT%H:%M'),'max_date':now.strftime('%Y-%m-%dT%H:%M'),'range_start':form.cleaned_data.get('start_date_parsed'),'range_end':form.cleaned_data.get('end_date_parsed'),'filter_errors':form.errors,'section':'logs','product_name':'Ufuk-FileAudit'}

@login_required
def logs(request):
    form,qs=filtered(request);qs=qs.order_by('-when','-id')
    if form.is_valid() and request.GET.get('export')=='pdf':
        from .pdf import logs_pdf
        return logs_pdf(qs,form.cleaned_data,request.user.username)
    if form.is_valid() and request.GET.get('export')=='csv':
        r=HttpResponse(content_type='text/csv; charset=utf-8');r['Content-Disposition']='attachment; filename="Ufuk-FileAudit-Loglar.csv"';r.write('\ufeff')
        w=csv.writer(r);w.writerow(['Tarih ve saat','Kullanıcı','İşlem','Paylaşım','Dosya','Yeni yol','İstemci IP','Durum','Dosya sunucusu'])
        def cell(value):
            value='' if value is None else str(value)
            return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
        for e in qs.select_related('source').iterator(chunk_size=2000):w.writerow([cell(v) for v in [timezone.localtime(e.when).strftime('%d.%m.%Y %H:%M:%S'),e.who,ACTIONS.get(e.action,e.action),e.share_name,e.what,e.new_path,e.host,{'Success':'Başarılı','Failed':'Başarısız'}.get(e.status,e.status),e.source.client if e.source else e.where]])
        return r
    ctx=base_context(request,form);ctx['page_obj']=Paginator(qs.select_related('source'),50).get_page(request.GET.get('page'));ctx['total']=qs.count()
    return render(request,'reports/logs.html',ctx,status=200 if form.is_valid() else 400)

def rankings(qs,action):
    rows=list(qs.filter(action=action).values('who').annotate(total=Count('id')).order_by('-total','who')[:10])
    maximum=max([r['total'] for r in rows],default=1)
    for r in rows:r['width']=max(1,round(r['total']/maximum*100,2))
    return rows

def analytics_context(request,form,qs):
    ctx=base_context(request,form);ctx['section']='graphs'
    totals=dict(qs.values('action').annotate(n=Count('id')).values_list('action','n'))
    ctx.update(total=sum(totals.values()),deletes=totals.get('Removed',0),copies=totals.get('Copied',0),creates=totals.get('Created',0),top_deletes=rankings(qs,'Removed'),top_copies=rankings(qs,'Copied'),top_creates=rankings(qs,'Created'))
    ctx['copy_scope']='Seçili tarih ve filtreler · doğrulanmış kopyalama'
    if form.is_valid() and not ctx['top_copies']:
        ctx['top_copies']=rankings(LogEntry.objects.filter(when__gte=cutoff()),'Copied')
        ctx['copies_fallback']=True
        ctx['copy_scope']='Seçili aralıkta kopyalama yok: tüm sunucular, saklanan tüm dönem (en fazla 1 yıl)'
    timeline=list(qs.annotate(day=TruncDate('when',tzinfo=timezone.get_current_timezone())).values('day').annotate(total=Count('id')).order_by('day'))
    highest=max([r['total'] for r in timeline],default=1)
    for row in timeline:row['width']=max(1,round(row['total']/highest*100,2))
    ctx['timeline']=timeline
    end=form.cleaned_data.get('end_date_parsed') or timezone.now()
    snapshots=InventorySnapshot.objects.filter(completed_at__gte=cutoff(),completed_at__lte=end).select_related('source')
    if form.cleaned_data.get('server'):snapshots=snapshots.filter(source_id=form.cleaned_data['server'])
    # Take one latest completed measurement per server, including legacy unassigned data.
    latest=snapshots.order_by().values('source_id').annotate(latest=Max('completed_at'))
    selected=[]
    for row in latest:
        item=snapshots.filter(source_id=row['source_id'],completed_at=row['latest']).order_by('-id').first()
        if item:selected.append(item)
    ctx['snapshots']=selected
    from types import SimpleNamespace
    snap=(selected[0] if len(selected)==1 else SimpleNamespace(completed_at=min(s.completed_at for s in selected),files=sum(s.files for s in selected),errors=sum(s.errors for s in selected),skipped=sum(s.skipped for s in selected))) if selected else None
    ctx['snapshot']=snap
    owners=[]
    if snap:
        rows=OwnerUsage.objects.filter(snapshot__in=selected)
        if form.cleaned_data.get('share_name'):rows=rows.filter(share__iexact=form.cleaned_data['share_name'])
        if form.cleaned_data.get('who'):rows=rows.filter(owner__icontains=form.cleaned_data['who'])
        order='-files' if request.GET.get('owner_order')=='files' else '-allocated_bytes'
        owners=list(rows.values('owner').annotate(files=Sum('files'),logical_bytes=Sum('logical_bytes'),allocated_bytes=Sum('allocated_bytes'),allocation_errors=Sum('allocation_errors')).order_by(order,'owner'))
        maximum=max([r['allocated_bytes'] for r in owners],default=1) or 1
        for r in owners:r['width']=max(1,round(r['allocated_bytes']/maximum*100,2))
    ctx['owners']=owners;ctx['top_owners']=owners[:15]
    requests=ScanRequest.objects.order_by('-created_at')
    clients=APIToken.objects.filter(is_active=True)
    if form.cleaned_data.get('server'):
        requests=requests.filter(source_id=form.cleaned_data['server']);clients=clients.filter(pk=form.cleaned_data['server'])
    ctx['scan_request']=requests.first();ctx['active_client']=clients.order_by('-last_activity').first()
    return ctx

@login_required
def graphs(request):
    form,qs=filtered(request);ctx=analytics_context(request,form,qs)
    if form.is_valid() and request.GET.get('export')=='pdf':
        from .pdf import analytics_pdf
        return analytics_pdf(ctx,request.user.username)
    return render(request,'reports/graphs.html',ctx,status=200 if form.is_valid() else 400)

@login_required
def home(request):return redirect('reports:graphs')

@login_required
def owner_detail(request):
    form,qs=filtered(request)
    if not form.is_valid():return render(request,'reports/owner_detail.html',{'filter_errors':form.errors},status=400)
    ctx=analytics_context(request,form,qs)
    owner=request.GET.get('owner','')
    if len(owner)>256:return JsonResponse({'detail':'Geçersiz dosya sahibi'},status=400)
    rows=FolderUsage.objects.filter(snapshot__in=ctx['snapshots']).select_related('snapshot__source').order_by('-allocated_bytes','share','path')
    if form.cleaned_data.get('share_name'):rows=rows.filter(share__iexact=form.cleaned_data['share_name'])
    if owner:rows=rows.filter(owner=owner)
    term=request.GET.get('folder','')[:500]
    if term:rows=rows.filter(path__icontains=term)
    if request.GET.get('export')=='csv':
        response=HttpResponse(content_type='text/csv; charset=utf-8');response['Content-Disposition']='attachment; filename="Ufuk-FileAudit-Klasorler.csv"';response.write('\ufeff')
        writer=csv.writer(response);writer.writerow(['Dosya sahibi','Sunucu','Paylaşım','Klasör','Dosya sayısı','Ayrılan bayt','Dosya boyutları bayt','Ölçüm tarihi'])
        def safe(v):
            v=str(v);return "'"+v if v.lstrip().startswith(('=','+','-','@')) else v
        for row in rows.iterator(chunk_size=1000):writer.writerow([safe(v) for v in [row.owner,row.snapshot.source.client if row.snapshot.source else row.snapshot.host,row.share,row.path,row.files,row.allocated_bytes,row.logical_bytes,row.snapshot.completed_at]])
        return response
    params=request.GET.copy();params.pop('page',None);params.pop('export',None)
    ctx.update(owner=owner,unresolved_sid=owner.startswith('S-1-'),folder_rows=Paginator(rows,100).get_page(request.GET.get('page')),folder_count=rows.count(),folder_search=term,detail_query=params.urlencode(),full_depth=bool(ctx['snapshots']) and all(s.folder_detail_level=='full' for s in ctx['snapshots']),details_complete=bool(ctx['snapshots']) and all(s.folder_details_complete for s in ctx['snapshots']))
    return render(request,'reports/owner_detail.html',ctx)

@require_POST
@user_passes_test(lambda u:u.is_active and u.is_staff)
def request_scan(request):
    servers=APIToken.objects.filter(is_active=True,server_ip__isnull=False)
    if request.POST.get('server'):
        if not request.POST['server'].isdigit():return JsonResponse({'detail':'Geçersiz sunucu'},status=400)
        servers=servers.filter(pk=request.POST['server'])
    for server in servers:
        if not ScanRequest.objects.filter(source=server,created_at__gte=timezone.now()-timedelta(minutes=15)).exists():ScanRequest.objects.create(source=server,requested_by=request.user.username)
    return redirect('/grafikler/?scan=requested')

@csrf_exempt
@require_POST
def inventory_ingest(request):
    # The existing token middleware enforces token activity and source IP.
    if not request.path.startswith('/monitor/api/'):return JsonResponse({'detail':'Geçersiz uç nokta'},status=403)
    if len(request.body)>4*1024*1024:return JsonResponse({'detail':'Veri sınırı aşıldı'},status=413)
    try:
        data=json.loads(request.body);sid=uuid.UUID(str(data['scan_id']));start=parse_datetime(data['started_at']);end=parse_datetime(data['completed_at'])
        if not start or not end or timezone.is_naive(start) or timezone.is_naive(end) or start>end or end>timezone.now()+timedelta(minutes=5) or end<cutoff():raise ValueError('Geçersiz tarama zamanı')
        owners=data['owners']
        if not isinstance(owners,list) or len(owners)>10000:raise ValueError('Geçersiz sahip listesi')
        clean=[]
        for row in owners:
            allowed=request.audit_client.share_paths or dict.fromkeys(settings.AUDIT_SHARES)
            if row['share'].casefold() not in {str(x).casefold() for x in allowed}:raise ValueError('Geçersiz paylaşım')
            numeric={k:int(row.get(k,0)) for k in ['files','logical_bytes','allocated_bytes','allocation_errors']}
            if any(v<0 or v>9223372036854775807 for v in numeric.values()):raise ValueError('Geçersiz boyut')
            clean.append(OwnerUsage(owner=str(row['owner'])[:256],share=row['share'],**numeric))
        errors=int(data.get('errors',0));skipped=int(data.get('skipped',0))
        folder_data=data.get('folders',[])
        if 'folders_gzip' in data:
            packed=base64.b64decode(data['folders_gzip'],validate=True)
            with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:raw=stream.read(64*1024*1024+1)
            if len(raw)>64*1024*1024:raise ValueError('Klasör verisi çok büyük')
            folder_data=json.loads(raw)
        if not isinstance(folder_data,list) or len(folder_data)>200000:raise ValueError('Geçersiz klasör listesi')
        detail_level=data.get('folder_detail_level','top')
        if detail_level not in ('top','full'):raise ValueError('Geçersiz ayrıntı düzeyi')
        folder_rows=[];allowed=request.audit_client.share_paths or dict.fromkeys(settings.AUDIT_SHARES)
        for row in folder_data:
            if row['share'].casefold() not in {str(x).casefold() for x in allowed}:raise ValueError('Geçersiz paylaşım')
            numeric={k:int(row.get(k,0)) for k in ['files','logical_bytes','allocated_bytes','allocation_errors']}
            if any(v<0 or v>9223372036854775807 for v in numeric.values()):raise ValueError('Geçersiz boyut')
            path=str(row['path'])
            if not path or len(path)>32767:raise ValueError('Geçersiz yol')
            folder_rows.append(FolderUsage(owner=str(row['owner'])[:256],share=row['share'],path=path,**numeric))
        if errors<0 or skipped<0:raise ValueError('Geçersiz sayaç')
        with transaction.atomic():
            snap,created=InventorySnapshot.objects.get_or_create(scan_id=sid,defaults={'folder_detail_level':detail_level,'folder_details_complete':data.get('folder_details_complete') is True,'source':request.audit_client,'started_at':start,'completed_at':end,'host':request.META['REMOTE_ADDR'],'errors':errors,'skipped':skipped,'files':sum(r.files for r in clean)})
            if snap.source_id!=request.audit_client.pk:raise ValueError('Ölçüm başka sunucuya ait')
            if created:
                for r in clean:r.snapshot=snap
                OwnerUsage.objects.bulk_create(clean,batch_size=500)
                for r in folder_rows:r.snapshot=snap
                FolderUsage.objects.bulk_create(folder_rows,batch_size=200)
        return JsonResponse({'ok':True,'created':created},status=201 if created else 200)
    except (KeyError,ValueError,TypeError,OverflowError,json.JSONDecodeError,binascii.Error,OSError,EOFError) as exc:return JsonResponse({'detail':'Geçersiz envanter verisi'},status=400)

@csrf_exempt
def scan_poll(request):
    if request.method!='GET':return JsonResponse({'detail':'GET gerekli'},status=405)
    row=ScanRequest.objects.filter(source=request.audit_client,acknowledged_at__isnull=True).order_by('created_at').first()
    return JsonResponse({'request_id':row.id if row else None})

@csrf_exempt
@require_POST
def scan_ack(request):
    try:
        data=json.loads(request.body)
        ScanRequest.objects.filter(id=int(data['request_id']),source=request.audit_client).update(acknowledged_at=timezone.now())
        return JsonResponse({'ok':True})
    except (ValueError,TypeError,KeyError):return JsonResponse({'detail':'Geçersiz istek'},status=400)
