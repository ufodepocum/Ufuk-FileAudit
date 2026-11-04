"""Ordered SMB capture: packet payloads are not written to disk."""
import subprocess,ipaddress
from pathlib import Path
from normalize_pdml import Normalizer
ROOT=Path(__file__).resolve().parent.parent
class PacketCapture:
    def __init__(self,interface,output_file=None,filter_expr='smb2',server_ip=None,**kwargs):
        self.interface=interface;self.server_ip=str(ipaddress.IPv4Address(server_ip));self.process=None
    def capture_packets(self):
        with open(ROOT/'logs/capture-error.log','w',encoding='utf-8') as errors:
            self.process=subprocess.Popen([str(ROOT/'Wireshark/tshark.exe'),'-l','-n','-i',self.interface,'-f','tcp port 445 and host '+self.server_ip,'-Y','smb2','-T','pdml'],stdout=subprocess.PIPE,stderr=errors,text=True,encoding='utf-8',errors='replace',bufsize=1)
            try:
                normalizer=Normalizer();buffer=None
                for line in self.process.stdout:
                    line=line.strip()
                    if line=='<packet>':buffer=[line]
                    elif buffer is not None:
                        buffer.append(line)
                        if line=='</packet>':
                            yield from normalizer.packets('\n'.join(buffer));buffer=None
            finally:self.cleanup()
    def cleanup(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill()
