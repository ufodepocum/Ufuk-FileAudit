"""NTLM-encrypted WinRM, with bounded chunks and no credentials on disk."""
import base64,json
class RemoteError(RuntimeError):pass
class WindowsRemote:
    def __init__(self,ip,username,password,port=5985,https=False):
        import winrm
        self.password=password
        self.session=winrm.Session(f'{"https" if https else "http"}://{ip}:{port}/wsman',auth=(username,password),transport='ntlm',message_encryption='always',server_cert_validation='validate',operation_timeout_sec=60,read_timeout_sec=75)
    def run(self,script,config=None):
        if config is not None:
            blob=base64.b64encode(json.dumps(config,ensure_ascii=False).encode()).decode()
            script="$cfg=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+blob+"')) | ConvertFrom-Json)\n"+script
        protocol=self.session.protocol;shell=protocol.open_shell();command=None
        wrapper="try {$ErrorActionPreference='Stop'; [scriptblock]::Create([Console]::In.ReadToEnd()).Invoke()} catch {[Console]::Error.WriteLine($_.Exception.Message); exit 1}"
        encoded=base64.b64encode(wrapper.encode('utf-16le')).decode()
        try:
            command=protocol.run_command(shell,'powershell',['-NoProfile','-NonInteractive','-EncodedCommand',encoded],console_mode_stdin=False)
            data=script.encode('utf-8')
            for offset in range(0,len(data),16000):protocol.send_command_input(shell,command,data[offset:offset+16000],end=offset+16000>=len(data))
            out,err,code=protocol.get_command_output(shell,command)
            if code:
                message=err.decode(errors='replace').replace(self.password,'[gizlendi]')
                raise RemoteError('Windows adımı başarısız: '+message[-800:])
            return out.decode('utf-8',errors='replace').strip()
        finally:
            if command:
                try:protocol.cleanup_command(shell,command)
                except Exception:pass
            try:protocol.close_shell(shell)
            except Exception:pass
    def put_files(self,files):
        lines=[]
        for path,data in files.items():
            path=path.replace("'","''");data=data if isinstance(data,bytes) else data.encode('utf-8')
            blob=base64.b64encode(data).decode()
            lines.append("[IO.File]::WriteAllBytes('"+path+"',[Convert]::FromBase64String('"+blob+"'))")
        return self.run('\n'.join(lines))
