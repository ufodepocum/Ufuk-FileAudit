"""Recover SMB metadata omitted from PDML and split compound SMB commands."""
import copy,struct,xml.etree.ElementTree as E

class Normalizer:
    def __init__(self):
        self.setinfo={};self.ioctl={};self.resume={};self.names={};self.creates={};self.copied=set()
    @staticmethod
    def put(proto,name,show,showname=None):
        f=next((f for f in proto.iter('field') if f.get('name')==name),None)
        if f is None:f=E.SubElement(proto,'field',name=name)
        f.set('show',str(show));f.set('showname',str(show if showname is None else showname))
    def packets(self,xml):
        root=E.fromstring(xml)
        payload=next((f for f in root.iter('field') if f.get('name')=='tcp.payload'),None)
        raw=bytes.fromhex(payload.get('value','')) if payload is not None else b''
        base=int(payload.get('pos','0')) if payload is not None else 0
        common=[p for p in root if p.get('name')!='smb2']
        prev_session=prev_tree=None; related_name=None
        for proto in [p for p in root if p.get('name')=='smb2']:
            def get(n):
                f=next((f for f in proto.iter('field') if f.get('name')==n),None)
                return f.get('show') if f is not None else None
            cmd=int(get('smb2.cmd') or -1)
            response=get('smb2.flags.response') in ('True','1')
            session=get('smb2.sesid');tree=get('smb2.tid')
            if session and int(session,16)==0xffffffffffffffff and prev_session:
                session=prev_session;self.put(proto,'smb2.sesid',session)
            if tree and int(tree,16)==0xffffffff and prev_tree:
                tree=prev_tree;self.put(proto,'smb2.tid',tree)
            if session:prev_session=session
            if tree:prev_tree=tree
            start=int(proto.get('pos','0'))-base
            body=start+64
            try:
                if raw[start:start+4]==b'\xfeSMB' and not response:
                    if cmd==5:
                        off,n=struct.unpack_from('<HH',raw,body+44)
                        name=raw[start+off:start+off+n].decode('utf-16le')
                        if name:self.put(proto,'smb2.filename',name)
                        related_name=name
                        self.creates[(session,get('smb2.msg_id'))]=name
                    elif cmd==17:
                        cls=raw[body+3];off=struct.unpack_from('<H',raw,body+8)[0]
                        self.setinfo[(session,get('smb2.msg_id'))]=cls
                        if cls==10:
                            n=struct.unpack_from('<I',raw,start+off+16)[0]
                            self.put(proto,'smb2.filename',raw[start+off+20:start+off+20+n].decode('utf-16le'))
                            self.put(proto,'smb2.file_rename_info','10','SMB2_FILE_RENAME_INFO')
                        if cls==13 and raw[start+off]&1:
                            self.put(proto,'smb2.file_disposition_info','13','SMB2_FILE_DISPOSITION_INFO')
                        if related_name and raw[body+16:body+32]==b'\xff'*16:
                            self.put(proto,'pilot.related.filename',related_name)
                    elif cmd==11:
                        ctl=struct.unpack_from('<I',raw,body+4)[0];fid=raw[body+8:body+24].hex()
                        name=get('smb2.filename') or self.names.get((session,fid),'')
                        off,count=struct.unpack_from('<II',raw,body+24)
                        key=raw[start+off:start+off+24].hex() if count>=24 else ''
                        self.ioctl[(session,get('smb2.msg_id'))]=(ctl,fid,name,key)
                    elif cmd==6:
                        fid=raw[body+8:body+24].hex()
                        self.copied.discard((session,fid));self.names.pop((session,fid),None)
                elif response and cmd==5 and get('smb2.nt_status')=='0x00000000':
                    name=self.creates.pop((session,get('smb2.msg_id')),'') or get('smb2.filename')
                    fid=raw[body+64:body+80].hex()
                    if name and len(fid)==32:self.names[(session,fid)]=name
                elif response and cmd==11:
                    entry=self.ioctl.pop((session,get('smb2.msg_id')),None)
                    if entry and get('smb2.nt_status')=='0x00000000':
                        ctl,fid,name,key=entry
                        off,count=struct.unpack_from('<II',raw,body+32)
                        result=raw[start+off:start+off+count]
                        if ctl==0x00140078 and len(result)>=24:
                            self.resume[(session,result[:24].hex())]=name
                        elif ctl in (0x001440f2,0x001480f2) and len(result)>=12:
                            source=self.resume.get((session,key),'')
                            total=struct.unpack_from('<I',result,8)[0]
                            if source and name and total>0 and (session,fid) not in self.copied:
                                self.put(proto,'pilot.copy.source',source)
                                self.put(proto,'pilot.copy.target',name)
                                self.copied.add((session,fid))
                elif response and cmd==17:
                    cls=self.setinfo.pop((session,get('smb2.msg_id')),None)
                    if cls is not None:self.put(proto,'smb2.file_info.infolevel',f'0x{cls:02x}')
            except (ValueError,IndexError,struct.error,UnicodeDecodeError):
                pass
            for cache in (self.setinfo,self.ioctl,self.resume,self.names,self.creates):
                if len(cache)>50000:
                    for key in list(cache)[:10000]:cache.pop(key,None)
            packet=E.Element('packet')
            packet.extend(copy.deepcopy(common));packet.append(copy.deepcopy(proto))
            yield E.tostring(packet,encoding='unicode')
