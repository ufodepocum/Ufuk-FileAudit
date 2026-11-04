import unittest,tempfile,json,sys
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from installer import wizard
from installer.remote import WindowsRemote,RemoteError

class InstallerTests(unittest.TestCase):
    def test_ipv4_and_share_names_are_validated(self):
        self.assertEqual(wizard.ipv4('192.0.2.10'),'192.0.2.10')
        for value in ['192.0.2.10;whoami','0.0.0.0','127.0.0.1','224.0.0.1','300.0.0.1']:
            with self.assertRaises(wizard.SetupError):wizard.ipv4(value)
        shares=[{'Name':'Veri','Path':r'D:\Veri'},{'Name':'Pazarlama$','Path':r'E:\Pazarlama'}]
        self.assertEqual(list(wizard.choose_shares('veri, Pazarlama$',shares)),['Veri','Pazarlama$'])
        with self.assertRaises(wizard.SetupError):wizard.choose_shares('bilinmeyen',shares)
        with self.assertRaises(wizard.SetupError):wizard.choose_shares('Veri,veri',shares)
    def test_npcap_is_rechecked_until_actual_ready(self):
        remote=SimpleNamespace(run=unittest.mock.Mock(side_effect=['INSTALL_REQUIRED','INSTALL_REQUIRED','READY']))
        confirm=unittest.mock.Mock(return_value='')
        wizard.wait_for_npcap(remote,'script',confirm)
        self.assertEqual(remote.run.call_count,3);self.assertEqual(confirm.call_count,2)
    def test_npcap_quit_does_not_report_success(self):
        remote=SimpleNamespace(run=lambda script:'INSTALL_REQUIRED')
        with self.assertRaises(wizard.SetupError):wizard.wait_for_npcap(remote,'script',lambda prompt:'q')
    def test_config_keeps_secret_and_contains_no_admin_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            wizard.configure_server(root,'192.0.2.10','192.0.2.20',8085,{'Veri$':r'D:\Veri'})
            first=(root/'runtime.env').read_text()
            wizard.configure_server(root,'192.0.2.10','192.0.2.20',8086,{'Veri$':r'D:\Veri'})
            self.assertEqual(first,(root/'runtime.env').read_text())
            self.assertNotIn('password',first.lower());self.assertIn('Veri$',first)
            with self.assertRaises(wizard.SetupError):wizard.configure_server(root,'192.0.2.11','192.0.2.20',8085,{'Veri':r'D:\Veri'})
    def test_unknown_installation_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';target=Path(tmp)/'destination'
            (source/'app').mkdir(parents=True);(source/'installer').mkdir();(source/'app/manage.py').write_text('pass');(source/'installer/wizard.py').write_text('pass')
            target.mkdir();(target/'private.txt').write_text('keep')
            with self.assertRaises(wizard.SetupError):wizard.stage(source,target)
            self.assertEqual((target/'private.txt').read_text(),'keep')
    def test_complete_wizard_does_not_store_management_credentials(self):
        instances=[]
        class FakeRemote:
            def __init__(self,*args,**kwargs):self.files={};self.calls=[];instances.append(self)
            def put_files(self,files):self.files.update(files)
            def run(self,script,config=None):
                self.calls.append(script)
                if '$identity=' in script:return json.dumps({'computer':'FS01','os':'Windows Server 2019','shares':[{'Name':'Veri','Path':r'D:\Veri'}],'interfaces':[{'InterfaceAlias':'Ethernet','IPAddress':'192.0.2.10'}],'tasks':[],'npcap':True})
                if 'INSTALL_REQUIRED' in script:return 'READY'
                if 'AGENT_STARTED' in script:return json.dumps({'backup':r'C:\ProgramData\Ufuk-FileAudit\backups\test'})
                if 'api_status' in script:return json.dumps({'api_status':201,'capture':'Running'})
                return 'OK'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=Path(__file__).resolve().parents[1]
            import shutil
            shutil.copytree(source/'installer/windows',root/'installer/windows')
            (root/'agent').mkdir();(root/'agent/requirements.txt').write_text('pywin32==308');(root/'agent/launcher.py').write_text('pass');(root/'agent/uninstall.ps1').write_text('')
            with patch('installer.remote.WindowsRemote',FakeRemote),patch('builtins.input',side_effect=['192.0.2.10',r'EXAMPLE\Admin','Veri','192.0.2.20','8085']),patch('getpass.getpass',return_value='DO-NOT-STORE-THIS'),patch.object(wizard,'check_docker'),patch.object(wizard,'compose'),patch.object(wizard,'wait_web'),patch.object(wizard,'read_token',return_value='7fe6391b-e972-42e2-90fb-d8e0f12c0ea4'),patch.object(wizard,'install_timer'):
                wizard.perform(root)
            all_text=''.join(f.read_text(encoding='utf-8') for f in root.rglob('*') if f.is_file())
            remote_text=''.join(str(v) for v in instances[0].files.values())
            self.assertNotIn('DO-NOT-STORE-THIS',all_text+remote_text)
            self.assertIn('SYSTEM',(root/'installer/windows/activate.ps1').read_text())
            self.assertIn('Veri',remote_text)
    def test_winrm_chunks_and_cleanup_and_error_redaction(self):
        class Protocol:
            def __init__(self,fail=False):self.chunks=[];self.closed=False;self.fail=fail
            def open_shell(self):return 's'
            def run_command(self,*args,**kwargs):return 'c'
            def send_command_input(self,s,c,data,end):self.chunks.append((data,end))
            def get_command_output(self,*args):return (b'OK',b'SecretTest' if self.fail else b'',1 if self.fail else 0)
            def cleanup_command(self,*args):pass
            def close_shell(self,*args):self.closed=True
        for failure in [False,True]:
            protocol=Protocol(failure);remote=WindowsRemote.__new__(WindowsRemote);remote.password='SecretTest';remote.session=SimpleNamespace(protocol=protocol)
            if failure:
                with self.assertRaises(RemoteError) as exc:remote.run('x'*41000)
                self.assertNotIn('SecretTest',str(exc.exception))
            else:self.assertEqual(remote.run('x'*41000),'OK')
            self.assertTrue(protocol.closed);self.assertEqual(len(protocol.chunks),3);self.assertTrue(protocol.chunks[-1][1]);self.assertTrue(all(len(x[0])<=16000 for x in protocol.chunks))

if __name__=='__main__':unittest.main()
