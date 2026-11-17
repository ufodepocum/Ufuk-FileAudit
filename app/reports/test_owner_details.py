from datetime import timedelta
from uuid import uuid4
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from monitor.models import APIToken,LogEntry
from .models import InventorySnapshot,FolderUsage

class OwnerDetailTests(TestCase):
    @override_settings(APP_DISPLAY_NAME='Firma Denetim')
    def test_custom_brand_is_used_in_login_dashboard_and_pdf_metadata(self):
        self.assertContains(self.client.get('/logs/'),'Firma Denetim')
        response=self.client.get('/logs/',self.params|{'export':'pdf'})
        self.assertIn(b'Firma Denetim',b''.join(response.streaming_content))
        self.client.logout();self.assertContains(self.client.get('/login/'),'Firma Denetim')
    def setUp(self):
        self.client.force_login(User.objects.create_user('reader',password='test-password'))
        self.now=timezone.now();self.params={'start_date':(self.now-timedelta(hours=1)).isoformat(),'end_date':self.now.isoformat()}
    def test_empty_period_copy_chart_uses_retained_entire_system_and_labels_scope(self):
        LogEntry.objects.create(when=self.now-timedelta(days=10),who='DEMO\\copy-user',action='Copied',what='sample',where='demo',share_name='Veri',object_type='File',host='192.0.2.1',status='Success')
        r=self.client.get('/grafikler/',self.params)
        self.assertEqual(r.context['copies'],0);self.assertTrue(r.context['copies_fallback'])
        self.assertEqual(r.context['top_copies'][0]['who'],'DEMO\\copy-user')
        self.assertContains(r,'tüm sunucular, saklanan tüm dönem')
    def test_owner_detail_respects_server_and_historical_measurement(self):
        servers=[APIToken.objects.create(client='a',server_ip='192.0.2.1'),APIToken.objects.create(client='b',server_ip='192.0.2.2')]
        for server in servers:
            for days in (2,0):
                end=self.now-timedelta(hours=2,days=days)
                snap=InventorySnapshot.objects.create(source=server,scan_id=uuid4(),started_at=end-timedelta(minutes=5),completed_at=end,host=server.server_ip,folder_details_complete=True)
                FolderUsage.objects.create(snapshot=snap,owner='S-1-5-21-demo',share='Veri',path='D:\\Veri\\'+server.client+str(days),files=3,allocated_bytes=1024**3)
        r=self.client.get('/grafikler/sahip/',self.params|{'owner':'S-1-5-21-demo','server':servers[0].pk})
        self.assertEqual(r.status_code,200);self.assertContains(r,'D:\\Veri\\a0');self.assertNotContains(r,'D:\\Veri\\b0');self.assertNotContains(r,'D:\\Veri\\a2')
        self.assertContains(r,'Windows bu SID')
        self.client.logout();self.assertEqual(self.client.get('/grafikler/sahip/',{'owner':'x'}).status_code,302)
    def test_compressed_full_folder_inventory_paginates_and_exports_all_paths(self):
        import json,gzip,base64,csv,io
        server=APIToken.objects.create(client='folders',server_ip='192.0.2.10',whitelisted_ips='127.0.0.1',share_paths={'Veri':'D:\\Veri'})
        folders=[{'owner':'DEMO\\owner','share':'Veri','path':f'D:\\Veri\\a\\nested-{n}','files':1,'logical_bytes':10,'allocated_bytes':4096} for n in range(105)]
        body={'scan_id':str(uuid4()),'started_at':(self.now-timedelta(minutes=5)).isoformat(),'completed_at':(self.now-timedelta(minutes=1)).isoformat(),'owners':[{'owner':'DEMO\\owner','share':'Veri','files':105,'logical_bytes':1050,'allocated_bytes':105*4096}],'folder_details_complete':True,'folder_detail_level':'full','folders_gzip':base64.b64encode(gzip.compress(json.dumps(folders).encode())).decode()}
        for _ in range(2):self.assertIn(self.client.post('/monitor/api/inventory/',data=json.dumps(body),content_type='application/json',HTTP_AUTHORIZATION='Token '+str(server.token)).status_code,(200,201))
        self.assertEqual(FolderUsage.objects.count(),105)
        params=self.params|{'owner':'DEMO\\owner','server':server.pk}
        r=self.client.get('/grafikler/sahip/',params);self.assertEqual(r.context['folder_count'],105);self.assertEqual(len(r.context['folder_rows']),100);self.assertTrue(r.context['full_depth'])
        r=self.client.get('/grafikler/sahip/',params|{'page':2});self.assertEqual(len(r.context['folder_rows']),5)
        r=self.client.get('/grafikler/sahip/',params|{'export':'csv'});self.assertEqual(len(list(csv.reader(io.StringIO(r.content.decode('utf-8-sig'))))),106)
        body['scan_id']=str(uuid4());body['folders_gzip']='invalid-compressed-data'
        self.assertEqual(self.client.post('/monitor/api/inventory/',data=json.dumps(body),content_type='application/json',HTTP_AUTHORIZATION='Token '+str(server.token)).status_code,400)
