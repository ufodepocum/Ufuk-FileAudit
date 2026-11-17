from datetime import timedelta
from uuid import uuid4
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from monitor.models import APIToken,LogEntry
from .models import InventorySnapshot,FolderUsage

class OwnerDetailTests(TestCase):
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
