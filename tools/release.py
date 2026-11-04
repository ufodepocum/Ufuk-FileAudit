#!/usr/bin/env python3
"""Build a relocatable static website, source archives and an HTTP Git mirror."""
import argparse,hashlib,html,json,os,shutil,subprocess,tarfile,zipfile
from pathlib import Path

SKIP_DIRS={'.git','__pycache__','.installer-venv','data','backups','downloads','dist'}
SKIP_FILES={'.env','runtime.env','installation.json','config.json'}
def source_files(root):
    result=[]
    tracked=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode('utf-8').split('\0')
    for name in filter(None,tracked):
        file=root/name
        rel=file.relative_to(root)
        if any(x in SKIP_DIRS for x in rel.parts) or file.name in SKIP_FILES:continue
        if file.suffix in ('.pyc','.sqlite3','.log','.zip') or file.name.endswith('.tar.gz'):continue
        if file.is_file():result.append(file)
    return sorted(result,key=lambda f:f.relative_to(root).as_posix())
def link(root,page):return os.path.relpath(root,page.parent).replace(os.sep,'/')
def page_for(rel,is_dir=False):
    parts=['dir-'+x for x in rel.parts] if is_dir else ['dir-'+x for x in rel.parts[:-1]]+['file-'+rel.name+'.html']
    return Path('source',*parts,*(('index.html',) if is_dir else ()))
def skeleton(title,body,css='site.css',home='index.html'):
    return '<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+' | Ufuk-FileAudit</title><link rel="stylesheet" href="'+css+'"></head><body><header class="top"><a class="brand" href="'+home+'"><b>U<span>F</span></b> Ufuk-FileAudit</a><span class="topnote">Açık kaynak · Kendi sunucunuzda</span></header>'+body+'</body></html>'

CSS='''*{box-sizing:border-box}body{margin:0;font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;color:#203347;background:#f6f8fa}a{color:#1764c7;text-decoration:none}a:hover{text-decoration:underline}button{font:inherit;cursor:pointer}.top{height:76px;background:#112738;color:#d0dce5;display:flex;align-items:center;justify-content:space-between;padding:0 max(24px,calc((100vw - 1240px)/2));gap:20px}.brand{display:flex;align-items:center;gap:12px;color:white;font-size:20px;font-weight:650;letter-spacing:-.5px}.brand:hover{text-decoration:none}.brand b{width:36px;height:37px;background:#2679ef;border-radius:9px;text-align:center;font-size:25px;line-height:37px;position:relative}.brand b span{font-size:11px;position:absolute;right:4px;bottom:-4px}.topnote{font-size:12px;color:#94adbf}.container{max-width:1240px;margin:auto;padding:34px 24px 50px}.repo-title{display:flex;align-items:center;gap:11px;margin-bottom:13px;font-size:24px;letter-spacing:-.5px}.badge{border:1px solid #cfdae4;color:#62798c;background:#fff;border-radius:20px;padding:1px 9px;font-size:11px;font-weight:500}.intro{font-size:14px;color:#61778a;margin:0 0 22px;max-width:780px}.tabs{display:flex;gap:28px;border-bottom:1px solid #d9e2ea;margin-bottom:25px;font-size:13px}.tabs a{padding:11px 2px;color:#62778b}.tabs .selected{border-bottom:2px solid #2c7bf1;color:#20384f;font-weight:600}.grid{display:grid;grid-template-columns:minmax(0,1fr) 290px;gap:26px}.card{background:white;border:1px solid #dce4eb;border-radius:9px;overflow:hidden;margin-bottom:22px}.card-head{padding:15px 19px;background:#f9fbfd;border-bottom:1px solid #e2e8ee;font-weight:600;font-size:13px;display:flex;justify-content:space-between;align-items:center;gap:12px}.commit{font-family:Consolas,monospace;font-size:11px;color:#6e8495}.tree{width:100%;border-collapse:collapse}.tree td{padding:10px 18px;border-bottom:1px solid #edf1f4;font-size:13px}.tree tr:last-child td{border-bottom:0}.tree tr:hover{background:#f7faff}.tree td:first-child{width:31px;padding-right:0;color:#5b8cbd}.tree td:last-child{color:#8798a7;font-size:11px;text-align:right}.inside{padding:22px}.inside h2{font-size:20px;margin:0 0 12px;letter-spacing:-.4px}.inside h3{font-size:14px;margin:23px 0 9px}.inside p,.inside li{font-size:13px;color:#60788b}.inside ul{padding-left:20px}.button{display:flex;align-items:center;justify-content:center;padding:10px 14px;border-radius:6px;border:1px solid #d1deea;font-weight:600;font-size:12px;color:#325572;background:#fff;margin-bottom:9px;text-align:center}.button:hover{background:#f1f6fc;text-decoration:none}.button.primary{background:#1d6ce0;border-color:#1d6ce0;color:white}.aside h3{font-size:13px;margin:0 0 10px}.aside p{font-size:12px;color:#6b8294}.version{font-size:26px;letter-spacing:-.7px;margin:5px 0 10px;font-weight:650}.version span{font-size:10px;color:#288365;background:#e5f5ed;padding:4px 7px;border-radius:5px;vertical-align:middle;margin-left:6px}.meta{padding-top:13px;border-top:1px solid #e2e8ef;font-size:11px;line-height:2;color:#7a90a2}.codebox{position:relative;border:1px solid #d7e3ef;border-radius:7px;background:#f3f7fc;margin:12px 0 17px;overflow:hidden}.codebox pre{font:12px/1.9 Consolas,monospace;margin:0;padding:18px 20px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}.copy{position:absolute;right:8px;top:8px;border:1px solid #cbd9e6;background:white;color:#58758c;font-size:10px;border-radius:4px;padding:3px 8px}.note{border-left:3px solid #4387e8;background:#eff5ff;padding:12px 15px;font-size:12px;color:#597b9c;margin:18px 0}.crumb{font-size:13px;color:#7a91a4;overflow-wrap:anywhere;margin-bottom:16px}.crumb a{margin-right:7px}.source-code{margin:0;padding:20px 24px;overflow:auto;font:12px/1.8 Consolas,"Cascadia Code",monospace;background:white;tab-size:4;white-space:pre}.file-type{font-size:11px;font-weight:500;color:#7991a6}footer{font-size:11px;color:#8da0b0;margin-top:28px;border-top:1px solid #dbe3eb;padding-top:18px}.small-link{font-size:11px}.step{display:flex;align-items:start;gap:13px;margin-top:15px}.step>b{display:grid;place-items:center;flex:0 0 25px;height:25px;background:#e9f1fd;color:#3173d0;border-radius:50%;font-size:11px}.step strong{font-size:13px}.step p{margin:3px 0}.file-page{max-width:1240px;margin:30px auto;padding:0 24px}.code-scroll{max-height:75vh;overflow:auto}.help-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.command-title{font-size:10px;color:#8da2b4;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}.readme-text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8}.repo-icon{font-size:19px;color:#6f8ca4}@media(max-width:850px){.grid{grid-template-columns:1fr}.aside{display:grid;grid-template-columns:1fr 1fr;gap:18px}.topnote{display:none}.container{padding:25px 17px}.repo-title{font-size:22px}.help-grid{grid-template-columns:1fr}.card-head{padding:13px 15px}.tree td{padding:9px 13px}}@media(max-width:500px){.aside{display:block}.top{padding:0 18px;height:66px}.brand{font-size:18px}.repo-title{font-size:19px}.repo-title .badge{font-size:9px}.tabs{gap:20px}.inside{padding:18px}.codebox pre{padding:40px 13px 14px;font-size:11px}.tree td:last-child{display:none}.file-page{padding:0 12px}.source-code{padding:15px;font-size:11px}.commit{font-size:9px}}
'''

def build_sources(root,out,files):
    directories={Path('.')}
    for f in files:directories.update(f.relative_to(root).parents)
    for directory in sorted(directories,key=lambda p:p.as_posix()):
        page=out/page_for(directory,True);page.parent.mkdir(parents=True,exist_ok=True)
        children={}
        for file in files:
            rel=file.relative_to(root)
            try:tail=rel.relative_to(directory)
            except ValueError:continue
            if len(tail.parts)==1:children[tail.parts[0]]=(rel,False,file.stat().st_size)
            elif tail.parts:children[tail.parts[0]]=(directory/tail.parts[0],True,0)
        rows=[]
        for name,(rel,is_dir,size) in sorted(children.items(),key=lambda x:(not x[1][1],x[0])):
            target=out/page_for(rel,is_dir)
            rows.append('<tr><td>'+('▱' if is_dir else '◇')+'</td><td><a href="'+html.escape(link(target,page),quote=True)+'">'+html.escape(name)+'</a></td><td>'+('Klasör' if is_dir else str(size)+' bayt')+'</td></tr>')
        body='<main class="file-page"><div class="crumb"><a href="'+link(out/'index.html',page)+'">Ufuk-FileAudit</a> / '+html.escape(directory.as_posix())+'</div><section class="card"><div class="card-head">Kaynak dosyaları <span class="badge">main</span></div><table class="tree">'+''.join(rows)+'</table></section></main>'
        page.write_text(skeleton('Kaynak kodu',body,link(out/'site.css',page),link(out/'index.html',page)),encoding='utf-8')
    for file in files:
        rel=file.relative_to(root);page=out/page_for(rel);page.parent.mkdir(parents=True,exist_ok=True)
        text=file.read_text(encoding='utf-8',errors='replace')
        body='<main class="file-page"><div class="crumb"><a href="'+link(out/'index.html',page)+'">Ufuk-FileAudit</a> / <a href="'+link(out/page_for(rel.parent,True),page)+'">'+html.escape(rel.parent.as_posix())+'</a> / '+html.escape(rel.name)+'</div><section class="card"><div class="card-head"><span>'+html.escape(rel.name)+'</span><span class="file-type">'+str(len(text.splitlines()))+' satır · UTF-8</span></div><div class="code-scroll"><pre class="source-code">'+html.escape(text)+'</pre></div></section></main>'
        page.write_text(skeleton(rel.name,body,link(out/'site.css',page),link(out/'index.html',page)),encoding='utf-8')

def homepage(version,commit,rows):
    body='''<main class="container"><div class="repo-title"><span class="repo-icon">▱</span> Ufuk-FileAudit <span class="badge">Kaynak kodu açık</span></div><p class="intro">Windows dosya sunucusu denetimi. Türkçe arayüz, kullanıcı grafikleri ve PDF raporları. Kendi Ubuntu sunucunuza adım adım kurun.</p><nav class="tabs"><a class="selected" href="source/index.html">⌘ Kaynak kodu</a><a href="#kurulum">Kurulum</a><a href="#surum">Sürüm ve indirme</a></nav><div class="grid"><div><section class="card"><div class="card-head"><span>⑂ main <span class="badge">v@@VERSION@@</span></span><span class="commit">@@COMMIT@@</span></div><table class="tree">@@ROWS@@</table></section><section class="card" id="kurulum"><div class="card-head">README · Kurulum</div><div class="inside"><h2>Bir web klasörü, tek kurucu.</h2><p>Bu sayfadaki paketi istediğiniz web klasöründe barındırabilirsiniz. Yeni Ubuntu sunucusunda aşağıdaki komutları çalıştırın; kurucu gerekli bilgileri sorar.</p><div class="codebox"><button class="copy" data-copy="install-command">Kopyala</button><pre id="install-command">Komut hazırlanıyor…</pre></div><div class="help-grid"><div class="step"><b>1</b><div><strong>Sunucu ve paylaşım seçimi</strong><p>Dosya sunucusu IP'si, domain/yerel yönetici hesabı ve izlenecek paylaşımlar.</p></div></div><div class="step"><b>2</b><div><strong>Npcap kontrolü</strong><p>Sürücü Windows'ta kontrol edilir; gerekirse kurulumu tamamlamanız beklenir.</p></div></div><div class="step"><b>3</b><div><strong>Otomatik kurulum</strong><p>Ubuntu web uygulaması, Windows ajanı ve disk envanteri görevleri hazırlanır.</p></div></div><div class="step"><b>4</b><div><strong>Doğrulama ve ilk giriş</strong><p>API ve ajan denetlenir. İlk hesap admin / admin; ilk girişte parola değişir.</p></div></div></div><div class="note">Npcap ücretsiz sürümünde grafik kurulum gerekir. Kurucu, imzalı yükleyicinin Windows'taki yolunu gösterir ve servisi yeniden kontrol etmeden devam etmez.</div><h3>Git ile kaynakları alın</h3><div class="codebox"><button class="copy" data-copy="git-command">Kopyala</button><pre id="git-command">Komut hazırlanıyor…</pre></div><a class="small-link" href="source/file-README.md.html">Tam kurulum, bakım ve kaldırma kılavuzu →</a></div></section></div><aside class="aside"><section class="card" id="surum"><div class="inside"><h3>SON SÜRÜM</h3><div class="version">v@@VERSION@@ <span>Kararlı paket</span></div><p>Kurucu, web uygulaması, Windows ajanı ve tam kaynak kodu aynı dağıtımda.</p><a class="button primary" href="Ufuk-FileAudit-@@VERSION@@.tar.gz" download>↓ Kaynak + kurucu · .tar.gz</a><a class="button" href="Ufuk-FileAudit-@@VERSION@@.zip" download>↓ ZIP olarak indir</a><a class="button" href="install.sh" download>install.sh</a><div class="meta"><a href="SHA256SUMS">SHA256 dosya doğrulaması</a><br><a href="source/file-CHANGELOG.md.html">Sürüm notları</a><br><a href="source/file-LICENSE.html">GPL-3.0 lisansı</a></div></div></section><section class="card"><div class="inside"><h3>GEREKSİNİMLER</h3><p>Ubuntu 22.04 / 24.04 LTS<br>Windows Server 2019+<br>WinRM yönetici erişimi<br>İnternet bağlantısı</p><h3>RAPORLAMA</h3><p>Tarih ve saat filtreleri<br>PDF / CSV indirme<br>Silme ve kopyalama grafikleri<br>Dosya sahibine göre disk alanı<br>En fazla 1 yıllık log</p></div></section></aside></div><footer>Ufuk-FileAudit · AuditSphere tabanlı açık kaynak dağıtım. Kaynak kodu ve lisans bilgileri bu pakette yer alır.</footer></main><script>
const base=new URL('.',location.href).href;
const quote=s=>"'"+s.replaceAll("'","'\\''")+"'";
document.getElementById('install-command').textContent=location.protocol.startsWith('http')?'curl -fL '+quote(base+'install.sh')+' -o install.sh\\nsudo bash install.sh --source '+quote(base):'Dosyaları web sunucunuza yüklediğinizde bu alan kurulum adresini otomatik gösterecek.';
document.getElementById('git-command').textContent='git clone '+quote(base+'ufuk-fileaudit.git');
document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{const text=document.getElementById(button.dataset.copy).textContent;try{await navigator.clipboard.writeText(text);button.textContent='Kopyalandı';setTimeout(()=>button.textContent='Kopyala',1600);}catch(e){button.textContent='Metni seçip kopyalayın';}}));
</script>'''
    return skeleton('Kaynak kodu ve kurulum',body.replace('@@VERSION@@',html.escape(version)).replace('@@COMMIT@@',html.escape(commit)).replace('@@ROWS@@',rows))

def build(root,destination):
    root=root.resolve();destination=destination.resolve()
    if subprocess.check_output(['git','-C',str(root),'status','--porcelain']).strip():raise RuntimeError('Yayın için önce kaynak değişikliklerini Git deposuna commit edin.')
    if destination==Path(destination.anchor) or destination==root or destination in root.parents:raise RuntimeError('Güvensiz çıktı dizini')
    destination.mkdir(parents=True,exist_ok=True)
    marker=destination/'.ufuk-release-output'
    if any(destination.iterdir()) and not marker.exists():raise RuntimeError('Çıktı dizini dolu ve bu araca ait değil.')
    marker.write_text('Ufuk-FileAudit release output\n')
    publish=destination/'publish'
    if publish.exists():
        resolved=publish.resolve()
        if resolved.parent!=destination or resolved.name!='publish':raise RuntimeError('Güvensiz yayın dizini')
        def retry_readonly(function,path,info):
            file=Path(path).resolve()
            if not file.is_relative_to(resolved) or not isinstance(info[1],PermissionError):raise info[1]
            file.chmod(0o700 if file.is_dir() else 0o600)
            function(path)
        shutil.rmtree(resolved,onerror=retry_readonly)
    publish.mkdir()
    version=(root/'VERSION').read_text().strip();prefix='Ufuk-FileAudit-'+version
    files=source_files(root)
    for file in files:
        if file.is_symlink():raise RuntimeError('Kaynak bağlantı içeriyor: '+str(file))
    with tarfile.open(publish/(prefix+'.tar.gz'),'w:gz') as tar:
        for file in files:
            info=tar.gettarinfo(str(file),arcname=prefix+'/'+file.relative_to(root).as_posix())
            info.mode=0o755 if file.suffix=='.sh' else 0o644;info.uid=info.gid=0;info.uname=info.gname=''
            with open(file,'rb') as data:tar.addfile(info,data)
    with zipfile.ZipFile(publish/(prefix+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for file in files:z.write(file,prefix+'/'+file.relative_to(root).as_posix())
    shutil.copyfile(root/'install.sh',publish/'install.sh')
    checks=[]
    for name in [prefix+'.tar.gz',prefix+'.zip','install.sh']:checks.append(hashlib.sha256((publish/name).read_bytes()).hexdigest()+'  '+name)
    (publish/'SHA256SUMS').write_text('\n'.join(checks)+'\n')
    bare=publish/'ufuk-fileaudit.git'
    subprocess.run(['git','init','--bare','--initial-branch=main',str(bare)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['git','--git-dir',str(bare),'fetch','--no-tags',str(root),'HEAD:refs/heads/main'],check=True,stdout=subprocess.DEVNULL)
    (bare/'FETCH_HEAD').unlink(missing_ok=True)
    (bare/'description').write_text('Ufuk-FileAudit - public source repository\n')
    subprocess.run(['git','--git-dir',str(bare),'repack','-ad'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['git','--git-dir',str(bare),'update-server-info'],check=True)
    commit=subprocess.check_output(['git','-C',str(root),'rev-parse','--short','HEAD'],text=True).strip()
    (publish/'site.css').write_text(CSS,encoding='utf-8');build_sources(root,publish,files)
    top={}
    for file in files:
        rel=file.relative_to(root);top[rel.parts[0]]=(Path(rel.parts[0]),len(rel.parts)>1)
    rows=[]
    for name,(rel,is_dir) in sorted(top.items(),key=lambda x:(not x[1][1],x[0])):
        rows.append('<tr><td>'+('▱' if is_dir else '◇')+'</td><td><a href="'+page_for(rel,is_dir).as_posix()+'">'+html.escape(name)+'</a></td><td>'+('Klasör' if is_dir else 'Kaynak dosyası')+'</td></tr>')
    (publish/'index.html').write_text(homepage(version,commit,''.join(rows)),encoding='utf-8')
    final=destination/'Ufuk-FileAudit-Web-Yayin-Paketi.zip'
    with zipfile.ZipFile(final,'w',zipfile.ZIP_DEFLATED) as z:
        for file in sorted(publish.rglob('*')):
            if file.is_file():z.write(file,'Ufuk-FileAudit-Web/'+file.relative_to(publish).as_posix())
    print(json.dumps({'publish':str(publish),'website_zip':str(final),'source_files':len(files),'version':version,'commit':commit},ensure_ascii=False))
    return publish,final

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();build(Path(__file__).resolve().parents[1],args.out)
