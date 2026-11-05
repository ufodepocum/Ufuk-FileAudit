import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
from django.test import TestCase,Client,override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from .models import APIToken,LogEntry
from reports.models import ScanRequest,InventorySnapshot,OwnerUsage

@override_settings(FILESERVER_IP='192.0.2.10',AUDIT_SHARES=['Veri'])
class ServerManagementTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('manager',password='test-only-password',is_staff=True)
        self.client.force_login(self.user)
        self.a=APIToken.objects.create(client='Dosya-1',server_ip='192.0.2.10',whitelisted_ips='127.0.0.1',share_paths={'Veri':'D:\\Veri'})
        self.b=APIToken.objects.create(client='Dosya-2',server_ip='192.0.2.11',whitelisted_ips='127.0.0.1',share_paths={'Veri':'E:\\Veri','Arsiv':'E:\\Arsiv'})
        self.url=f'/monitor/clients/setup/{self.a.pk}/'
        self.credentials={'username':'DEMO\\IT','password':'Never-save-this-password','panel_url':'http://192.0.2.30:8085','replace':'yes','shares':['Veri']}
        self.details={'computer':'FS-DEMO','os':'Windows Server 2019','npcap':True,'interfaces':[{'InterfaceAlias':'Ethernet','IPAddress':self.a.server_ip}],'shares':[{'Name':'Veri','Path':'D:\\Veri'}],'tasks':[]}
        self.now=timezone.now()
    def api(self,server,path,data=None,method='post'):
        return getattr(Client(),method)(path,data=json.dumps(data) if data is not None else None,content_type='application/json',HTTP_AUTHORIZATION='Token '+str(server.token))
    def test_registration_does_not_claim_installed_or_overwrite_other_server(self):
        r=self.client.post('/monitor/clients/',{'client':'Dosya-3','server_ip':'192.0.2.12'})
        self.assertEqual(r.status_code,302);new=APIToken.objects.get(client='Dosya-3');self.assertFalse(new.installed_at);self.assertEqual(new.share_paths,{})
        self.assertEqual(new.whitelisted_ips,new.server_ip)
        self.assertEqual(self.client.post('/monitor/clients/',{'client':'Duplicate','server_ip':self.a.server_ip}).status_code,200)
        self.assertEqual(APIToken.objects.count(),3)
        self.assertContains(self.client.get('/monitor/clients/'),'D:\\Veri')
    def test_staff_and_csrf_are_required_and_mutations_are_post_only(self):
        self.assertEqual(Client().post(self.url,self.credentials|{'action':'inspect'}).status_code,302)
        normal=User.objects.create_user('reader',password='test');self.client.force_login(normal)
        self.assertEqual(self.client.get('/monitor/clients/').status_code,302)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url,self.credentials|{'action':'inspect'}).status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f'/monitor/clients/disable/{self.a.pk}/').status_code,405)
    @patch('installer.remote.WindowsRemote')
    def test_concurrent_setup_cannot_overwrite_same_server(self,Remote):
        self.a.setup_started=timezone.now();self.a.save()
        self.assertEqual(self.client.post(self.url,self.credentials|{'action':'inspect'}).status_code,409)
        Remote.assert_not_called()
    @patch('installer.remote.WindowsRemote')
    def test_existing_tasks_require_explicit_replacement_confirmation(self,Remote):
        Remote.return_value.run.side_effect=[json.dumps(self.details|{'tasks':[{'TaskName':'Ufuk-FileAudit'}]}),'READY']
        r=self.client.post(self.url,self.credentials|{'action':'deploy','replace':''})
        self.assertEqual(r.status_code,400);Remote.return_value.put_files.assert_not_called()
    @patch('installer.remote.WindowsRemote')
    def test_dependency_preparation_does_not_mark_agent_installed(self,Remote):
        Remote.return_value.run.side_effect=[json.dumps(self.details),'READY','DEPENDENCIES_READY']
        self.assertEqual(self.client.post(self.url,self.credentials|{'action':'dependencies'}).status_code,200)
        self.a.refresh_from_db();self.assertFalse(self.a.installed_at)
    @patch('installer.remote.WindowsRemote')
    def test_discovery_is_read_only_and_password_is_not_persisted(self,Remote):
        Remote.return_value.run.return_value=json.dumps(self.details)
        r=self.client.post(self.url,self.credentials|{'action':'inspect'})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['details']['shares'],self.details['shares'])
        self.a.refresh_from_db();self.assertFalse(self.a.installed_at);self.assertIsNone(self.a.setup_started)
        self.assertNotIn(self.credentials['password'],json.dumps(self.client.session.items().__str__()))
        self.assertNotIn(self.credentials['password'],str(self.a.__dict__))
    @patch('installer.remote.WindowsRemote')
    def test_missing_npcap_blocks_deploy_and_returns_manual_instruction(self,Remote):
        remote=Remote.return_value
        remote.run.side_effect=[json.dumps(self.details|{'npcap':False}),'INSTALL_REQUIRED']
        r=self.client.post(self.url,self.credentials|{'action':'npcap'})
        self.assertFalse(r.json()['ready']);self.assertIn('RDP',r.json()['message'])
        remote.run.side_effect=[json.dumps(self.details|{'npcap':False})]
        self.assertEqual(self.client.post(self.url,self.credentials|{'action':'deploy'}).status_code,400)
        remote.put_files.assert_not_called()
    @patch('installer.remote.WindowsRemote')
    def test_only_discovered_shares_can_be_deployed(self,Remote):
        remote=Remote.return_value;remote.run.side_effect=[json.dumps(self.details),'READY']
        r=self.client.post(self.url,self.credentials|{'action':'deploy','shares':['Not-a-real-share']})
        self.assertEqual(r.status_code,400);remote.put_files.assert_not_called()
    @patch('installer.remote.WindowsRemote')
    def test_verified_deployment_records_actual_disk_paths(self,Remote):
        remote=Remote.return_value;remote.run.side_effect=[json.dumps(self.details),'READY','{}',json.dumps({'api_status':201,'capture':'Running'})]
        r=self.client.post(self.url,self.credentials|{'action':'deploy'})
        self.assertEqual(r.status_code,200,r.content)
        self.a.refresh_from_db();self.assertTrue(self.a.installed_at);self.assertEqual(self.a.share_paths,{'Veri':'D:\\Veri'})
        files=remote.put_files.call_args.args[0];config=json.loads(files[r'C:\ProgramData\Ufuk-FileAudit\stage\agent\config.json'])
        self.assertEqual(config['shares'],['Veri']);self.assertNotIn('password',config)
    @patch('installer.remote.WindowsRemote')
    def test_failed_verification_rolls_back_without_claiming_installed(self,Remote):
        remote=Remote.return_value;remote.run.side_effect=[json.dumps(self.details),'READY','{}',json.dumps({'api_status':500}),'ROLLBACK_COMPLETE']
        r=self.client.post(self.url,self.credentials|{'action':'deploy'})
        self.assertEqual(r.status_code,400);self.assertIn('geri yüklendi',r.json()['error'])
        self.a.refresh_from_db();self.assertFalse(self.a.installed_at);self.assertEqual(self.a.share_paths,{'Veri':'D:\\Veri'})
    def test_scan_requests_cannot_be_taken_or_acknowledged_by_another_server(self):
        scan=ScanRequest.objects.create(source=self.a,requested_by='manager')
        self.assertIsNone(self.api(self.b,'/monitor/api/scan/',method='get').json()['request_id'])
        self.api(self.b,'/monitor/api/scan/ack/',{'request_id':scan.pk});scan.refresh_from_db();self.assertIsNone(scan.acknowledged_at)
        self.assertEqual(self.api(self.a,'/monitor/api/scan/',method='get').json()['request_id'],scan.pk)
        self.api(self.a,'/monitor/api/scan/ack/',{'request_id':scan.pk});scan.refresh_from_db();self.assertIsNotNone(scan.acknowledged_at)
    def test_inventory_uses_each_servers_share_list_and_latest_snapshot(self):
        for server,gb in [(self.a,10),(self.b,20)]:
            for days,space in [(1,1),(0,gb)]:
                end=self.now-timedelta(hours=1,days=days)
                payload={'scan_id':str(uuid4()),'started_at':(end-timedelta(minutes=5)).isoformat(),'completed_at':end.isoformat(),'owners':[{'share':'Veri','owner':'DEMO\\ayse','files':2,'logical_bytes':space*1024**3,'allocated_bytes':space*1024**3}]}
                self.assertEqual(self.api(server,'/monitor/api/inventory/',payload).status_code,201)
        params={'start_date':(self.now-timedelta(days=2)).isoformat(),'end_date':self.now.isoformat()}
        r=self.client.get('/grafikler/',params);self.assertEqual(r.context['owners'][0]['allocated_bytes'],30*1024**3);self.assertEqual(len(r.context['snapshots']),2)
        r=self.client.get('/grafikler/',params|{'server':self.b.pk});self.assertEqual(r.context['owners'][0]['allocated_bytes'],20*1024**3)
    def test_event_source_is_server_authenticated_and_filters_do_not_mix(self):
        event={'when':(self.now-timedelta(minutes=1)).isoformat(),'who':'DEMO\\ayse','action':'Created','what':'Veri\\file.txt','where':'SAME-NAME','share_name':'Veri','object_type':'File','host':'192.0.2.100','status':'Success'}
        for server in [self.a,self.b]:
            for _ in range(2):self.assertEqual(self.api(server,'/monitor/api/log/',[event]).status_code,201)
        self.assertEqual(LogEntry.objects.count(),2)
        params={'start_date':(self.now-timedelta(hours=1)).isoformat(),'end_date':self.now.isoformat(),'server':self.a.pk}
        r=self.client.get('/logs/',params);self.assertEqual(r.context['total'],1);self.assertEqual(r.context['page_obj'][0].source,self.a)
        self.assertEqual(self.client.get('/logs/',params|{'server':'invalid'}).status_code,400)
