import importlib.util,tempfile,unittest
from pathlib import Path

AGENT=Path(__file__).resolve().parents[1]/'agent'
def load(name):
    spec=importlib.util.spec_from_file_location(name,AGENT/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class AgentPackageTests(unittest.TestCase):
    def test_standalone_distribution_contains_working_nested_pdml_parser(self):
        parser=load('pdml_parser').PDMLParser
        packet=parser.parse_string('<packet><proto name="smb2"><field name="smb2.cmd" show="5"/><field name="container"><field name="smb2.filename" show="örnek.txt"/></field><field name="smb2.cmd" show="6"/></proto></packet>')
        self.assertEqual(packet.smb2.get_field('smb2.cmd').get_attribute('show'),'5')
        self.assertEqual(packet.smb2.get_field('smb2.cmd',1).get_attribute('show'),'6')
        self.assertEqual(packet.smb2.get_field('smb2.filename').get_attribute('show'),'örnek.txt')
        self.assertEqual(packet.smb2.get_field('missing').get_attribute('show','Unknown'),'Unknown')
    def test_missing_parser_is_rejected_before_any_runtime_or_task_changes(self):
        validator=load('validate_runtime')
        with tempfile.TemporaryDirectory() as directory:
            for name in ['agent.py','launcher.py','capture.py','normalize_pdml.py','save_logs.py','inventory_worker.py']:(Path(directory)/name).write_text('')
            result=validator.check(directory)
        self.assertFalse(result['ok']);self.assertEqual(result['code'],'MISSING_AGENT_FILES');self.assertEqual(result['items'],['pdml_parser.py'])
