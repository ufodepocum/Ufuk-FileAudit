from datetime import timedelta
from uuid import uuid4
from io import StringIO
import csv,json
from django.test import TestCase,Client,override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from monitor.models import LogEntry,APIToken
from monitor.serializers import LogEntrySerializer
from .models import InventorySnapshot,OwnerUsage
from .retention import cutoff,purge

@override_settings(AUDIT_SHARES=['Veri','Pazarlama'])
class ReportsIntegrationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('test-user',password='OnlyForTests123',is_staff=True)
        self.client.force_login(self.user);self.now=timezone.now()
        self.event=dict(when=self.now-timedelta(minutes=2),who='EXAMPLE\\Çağrı',action='Created',what='Pazarlama\\çalışma.xlsx',where='WSUS',share_name='\\\\192.0.2.10\\Veri',object_type='File',host='192.0.2.20',status='Success')
        self.params={'start_date':timezone.localtime(self.now-timedelta(hours=3)).isoformat(),'end_date':timezone.localtime(self.now+timedelta(minutes=1)).isoformat()}
    def create(self,**kwargs):return LogEntry.objects.create(**(self.event|kwargs))
    def test_turkish_brand_and_all_pages(self):
        for path in ['/logs/','/grafikler/','/administration/users/','/monitor/clients/']:
            r=self.client.get(path,self.params);self.assertEqual(r.status_code,200,path);self.assertContains(r,'Ufuk-FileAudit');self.assertNotContains(r,'AuditSphere');self.assertContains(r,'lang="tr"')
    def test_csv_exports_all_filtered_rows_not_current_page(self):
        for n in range(67):self.create(what=f'Pazarlama\\dosya-{n}.txt')
        self.create(share_name='\\\\192.0.2.10\\Pazarlama')
        r=self.client.get('/logs/',self.params|{'share_name':'Veri','export':'csv'})
        rows=list(csv.reader(StringIO(r.content.decode('utf-8-sig'))));self.assertEqual(len(rows),68)
        self.assertEqual(rows[0][0],'Tarih ve saat');self.assertEqual(rows[1][2],'Oluşturuldu')
    def test_date_filters_both_boundaries_and_invalid_ranges(self):
        self.create();self.create(when=self.now-timedelta(days=2));self.create(who='EXAMPLE\\Başka')
        r=self.client.get('/logs/',self.params|{'who':'Çağrı'});self.assertEqual(r.context['total'],1)
        self.assertEqual(self.client.get('/logs/',{'start_date':'bozuk'}).status_code,400)
        self.assertEqual(self.client.get('/logs/',{'start_date':self.now.isoformat(),'end_date':(self.now-timedelta(days=1)).isoformat()}).status_code,400)
        self.assertEqual(self.client.get('/logs/',{'start_date':(cutoff()-timedelta(days=1)).isoformat()}).status_code,400)
        local=timezone.localtime(self.now)
        r=self.client.get('/logs/',{'start_date':(local-timedelta(hours=3)).strftime('%d.%m.%Y %H:%M'),'end_date':local.strftime('%d.%m.%Y %H:%M')})
        self.assertEqual(r.status_code,200);self.assertEqual(r.context['total'],2)
    def test_retention_removes_old_logs_and_snapshots(self):
        self.create(when=cutoff()-timedelta(seconds=1));self.create()
        old=InventorySnapshot.objects.create(scan_id=uuid4(),started_at=cutoff()-timedelta(days=2),completed_at=cutoff()-timedelta(days=1),host='192.0.2.10')
        OwnerUsage.objects.create(snapshot=old,owner='EXAMPLE\\IT',share='Veri',files=1,logical_bytes=1,allocated_bytes=4096)
        purge();self.assertEqual(LogEntry.objects.count(),1);self.assertEqual(OwnerUsage.objects.count(),0)
    def test_old_ingestion_is_rejected_and_api_requires_token(self):
        data=self.event|{'when':(cutoff()-timedelta(days=1)).isoformat()}
        serializer=LogEntrySerializer(data=data);self.assertFalse(serializer.is_valid());self.assertIn('when',serializer.errors)
        r=Client().post('/monitor/api/inventory/',data='{}',content_type='application/json');self.assertEqual(r.status_code,401)
    def test_real_ingestion_retry_is_idempotent(self):
        token=APIToken.objects.create(client='test',whitelisted_ips='127.0.0.1')
        body=self.event|{'when':self.event['when'].isoformat()}
        for _ in range(2):
            r=Client().post('/monitor/api/log/',data=json.dumps([body]),content_type='application/json',HTTP_AUTHORIZATION='Token '+str(token.token));self.assertEqual(r.status_code,201)
        self.assertEqual(LogEntry.objects.count(),1)
    def test_copy_rankings_do_not_count_creates(self):
        self.create();self.create(action='Copied',who='EXAMPLE\\Kopyalayan');self.create(action='Removed')
        r=self.client.get('/grafikler/',self.params)
        self.assertEqual(r.context['copies'],1);self.assertEqual(r.context['creates'],1)
        self.assertEqual(r.context['top_copies'][0]['who'],'EXAMPLE\\Kopyalayan')
    def test_snapshot_selection_is_at_report_end_not_current(self):
        first=InventorySnapshot.objects.create(scan_id=uuid4(),started_at=self.now-timedelta(hours=4),completed_at=self.now-timedelta(hours=3),host='192.0.2.10')
        newer=InventorySnapshot.objects.create(scan_id=uuid4(),started_at=self.now-timedelta(hours=1),completed_at=self.now-timedelta(minutes=30),host='192.0.2.10')
        OwnerUsage.objects.create(snapshot=first,owner='EXAMPLE\\Çağrı',share='Veri',files=12,logical_bytes=10*1024**3,allocated_bytes=10*1024**3)
        r=self.client.get('/grafikler/',{'start_date':(self.now-timedelta(days=1)).isoformat(),'end_date':(self.now-timedelta(hours=2)).isoformat()})
        self.assertEqual(r.context['snapshot'],first);self.assertContains(r,'10,00 GB')
    def test_pdf_is_downloadable_for_logs_and_analytics(self):
        self.create(what='Uzun\\'+('Çalışma ve değerlendirme klasörü\\'*15)+'rapor.xlsx')
        for path in ['/logs/','/grafikler/']:
            r=self.client.get(path,self.params|{'export':'pdf'});self.assertEqual(r.status_code,200);self.assertEqual(r['Content-Type'],'application/pdf')
            self.assertTrue(b''.join(r.streaming_content).startswith(b'%PDF-'));self.assertIn('Ufuk-FileAudit',r['Content-Disposition'])
    def test_new_inventory_is_idempotent_and_owner_based(self):
        token=APIToken.objects.create(client='inventory',whitelisted_ips='127.0.0.1')
        body={'scan_id':str(uuid4()),'started_at':(self.now-timedelta(minutes=1)).isoformat(),'completed_at':self.now.isoformat(),'owners':[{'share':'Pazarlama','owner':'EXAMPLE\\Sahip','files':10,'logical_bytes':20*1024**3,'allocated_bytes':18*1024**3}]}
        for _ in range(2):
            r=Client().post('/monitor/api/inventory/',data=json.dumps(body),content_type='application/json',HTTP_AUTHORIZATION='Token '+str(token.token));self.assertIn(r.status_code,(200,201))
        self.assertEqual(InventorySnapshot.objects.count(),1);self.assertEqual(OwnerUsage.objects.count(),1)
