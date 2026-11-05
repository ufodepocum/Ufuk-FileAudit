"""Check staged agent syntax/imports before stopping an existing agent."""
import ast,importlib.util,json,sys
from pathlib import Path

def check(directory):
    directory=Path(directory).resolve();sys.path.insert(0,str(directory))
    required={'agent.py','launcher.py','capture.py','normalize_pdml.py','pdml_parser.py','save_logs.py','inventory_worker.py'}
    missing=sorted(required-{p.name for p in directory.glob('*.py')})
    if missing:return {'ok':False,'code':'MISSING_AGENT_FILES','items':missing}
    modules=set()
    for path in directory.glob('*.py'):
        try:tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        except SyntaxError:return {'ok':False,'code':'AGENT_SYNTAX','items':[path.name]}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):modules.update(alias.name for alias in node.names)
            elif isinstance(node,ast.ImportFrom) and node.module:modules.add(node.module)
    missing=[]
    for name in sorted(modules):
        try:available=importlib.util.find_spec(name) is not None
        except (ImportError,ModuleNotFoundError,ValueError):available=False
        if not available:missing.append(name)
    if missing:return {'ok':False,'code':'MISSING_PYTHON_MODULES','items':missing}
    from pdml_parser import PDMLParser
    packet=PDMLParser.parse_string('<packet><proto name="smb2"><field name="smb2.cmd" show="5"/></proto></packet>')
    if packet.smb2.get_field('smb2.cmd').get_attribute('show')!='5':return {'ok':False,'code':'PARSER_SELF_TEST','items':[]}
    return {'ok':True,'code':'AGENT_RUNTIME_READY','items':[]}

if __name__=='__main__':
    result=check(sys.argv[1] if len(sys.argv)>1 else Path(__file__).parent)
    print(json.dumps(result));sys.exit(0 if result['ok'] else 1)
