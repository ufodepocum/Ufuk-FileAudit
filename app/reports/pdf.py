"""Bounded-memory, Unicode PDF reports for all rows in the selected range."""
from tempfile import SpooledTemporaryFile
from datetime import datetime
from django.http import FileResponse
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.colors import HexColor
from .forms import ACTIONS

for name,file in [('DejaVu','DejaVuSans.ttf'),('DejaVuBold','DejaVuSans-Bold.ttf')]:
    if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,'/usr/share/fonts/truetype/dejavu/'+file))
INK='#182f45';MUTED='#657c90';BLUE='#1763e8';BORDER='#e1e8ef'

def gb(n):return f'{(n or 0)/1024**3:,.2f}'.replace(',','_').replace('.',',').replace('_','.')+' GB'
def dt(d):return timezone.localtime(d).strftime('%d.%m.%Y %H:%M:%S') if d else '—'
def wrap(text,width,font='DejaVu',size=7):
    lines=[]
    for part in str('—' if text is None or text=='' else text).replace('\r','').split('\n'):
        if not part:lines.append('');continue
        while part:
            lo,hi=1,len(part)
            while lo<hi:
                mid=(lo+hi+1)//2
                if pdfmetrics.stringWidth(part[:mid],font,size)<=width:lo=mid
                else:hi=mid-1
            count=lo
            if count<len(part):
                cut=part.rfind(' ',0,count)
                if cut>count//2:count=cut+1
            lines.append(part[:count].rstrip());part=part[count:]
    return lines or ['—']

class Report:
    def __init__(self,title,start,end,requested_by):
        self.file=SpooledTemporaryFile(max_size=8*1024*1024,mode='w+b')
        self.c=canvas.Canvas(self.file,pagesize=landscape(A4),pageCompression=1)
        self.c.setTitle('Ufuk-FileAudit - '+title);self.c.setAuthor('Ufuk-FileAudit')
        self.w,self.h=landscape(A4);self.title=title;self.start=start;self.end=end;self.user=requested_by;self.page=0;self.y=0;self.columns=None
        self.new_page()
    def text(self,x,y,text,size=8,bold=False,color=INK):
        self.c.setFillColor(HexColor(color));self.c.setFont('DejaVuBold' if bold else 'DejaVu',size);self.c.drawString(x,y,str(text))
    def footer(self):
        self.c.setStrokeColor(HexColor(BORDER));self.c.line(32,32,self.w-32,32)
        self.text(32,19,'Ufuk-FileAudit · Türkiye saati (UTC+3) · '+self.user[:64],7,color=MUTED)
        self.text(self.w-85,19,'Sayfa '+str(self.page),7,color=MUTED)
    def new_page(self):
        if self.page:self.footer();self.c.showPage()
        self.page+=1
        self.c.setFillColor(HexColor(BLUE));self.c.roundRect(32,self.h-58,27,27,6,fill=1,stroke=0)
        self.text(39,self.h-49,'U',17,True,'#ffffff');self.text(70,self.h-45,'Ufuk-FileAudit',17,True)
        self.text(32,self.h-84,self.title,12,True)
        self.text(32,self.h-101,dt(self.start)+' — '+dt(self.end),8,color=MUTED)
        self.text(self.w-205,self.h-45,'Oluşturma: '+dt(timezone.now()),7,color=MUTED)
        self.y=self.h-121
        if self.columns:self.table_header()
    def paragraph(self,text,size=8,color=MUTED):
        for line in wrap(text,self.w-64,size=size):
            if self.y<55:self.new_page()
            self.text(32,self.y,line,size,color=color);self.y-=size+5
        self.y-=5
    def heading(self,title):
        if self.y<110:self.new_page()
        self.y-=7;self.text(32,self.y,title,11,True);self.y-=21
    def table(self,columns):
        self.columns=columns
        if self.y<100:self.new_page()
        else:self.table_header()
    def table_header(self):
        self.c.setFillColor(HexColor('#edf3fa'));self.c.rect(32,self.y-23,self.w-64,23,fill=1,stroke=0)
        x=32
        for title,width in self.columns:self.text(x+6,self.y-15,title,7,True);x+=width
        self.y-=23
    def row(self,values):
        arrays=[wrap(v,width-12) for v,(_,width) in zip(values,self.columns)]
        length=max(map(len,arrays));offset=0
        while offset<length:
            available=int((self.y-53-12)//10)
            if available<1:self.new_page();continue
            count=min(available,length-offset);height=count*10+12
            x=32
            for lines,(_,width) in zip(arrays,self.columns):
                for n,line in enumerate(lines[offset:offset+count]):self.text(x+6,self.y-14-n*10,line,7)
                x+=width
            self.c.setStrokeColor(HexColor(BORDER));self.c.line(32,self.y-height,self.w-32,self.y-height)
            self.y-=height;offset+=count
            if offset<length:self.new_page()
    def end_table(self):self.columns=None;self.y-=15
    def bars(self,title,rows,label='who'):
        self.heading(title)
        if not rows:self.paragraph('Seçili aralıkta kayıt yok.');return
        maximum=max(r['total'] for r in rows) or 1
        for row in rows:
            labels=wrap(str(row[label]),450,size=8)
            if self.y<65+len(labels)*12:self.new_page()
            for n,line in enumerate(labels):self.text(32,self.y-n*12,line,8)
            self.text(520,self.y,str(row['total']),8,True)
            self.y-=12*(len(labels)-1)
            self.c.setFillColor(HexColor('#eaf0f7'));self.c.roundRect(32,self.y-13,450,5,2,fill=1,stroke=0)
            self.c.setFillColor(HexColor(BLUE));self.c.roundRect(32,self.y-13,max(2,450*row['total']/maximum),5,2,fill=1,stroke=0);self.y-=31
    def finish(self,name):
        self.footer();self.c.save();self.file.seek(0)
        return FileResponse(self.file,as_attachment=True,filename=name,content_type='application/pdf')

def logs_pdf(qs,data,user):
    report=Report('Dosya işlem kayıtları',data['start_date_parsed'],data['end_date_parsed'],user)
    filters=[]
    for key,label in [('who','Kullanıcı'),('share_name','Paylaşım'),('action','İşlem'),('search','Arama'),('host','İstemci IP')]:
        if data.get(key):filters.append(label+': '+ACTIONS.get(data[key],data[key]))
    report.paragraph('Toplam kayıt: '+str(qs.count())+('. Filtreler: '+' · '.join(filters) if filters else '. Tüm kullanıcılar ve paylaşımlar.'))
    report.table([('Tarih / saat',91),('Kullanıcı',102),('İşlem',83),('Paylaşım',92),('Dosya ve ayrıntılar',316),('İstemci IP',93.89)])
    for entry in qs.iterator(chunk_size=2000):
        detail=entry.what or '—'
        for name,label in [('old_path','Önceki yol'),('new_path','Yeni yol'),('old_owner','Önceki sahip'),('new_owner','Yeni sahip'),('old_acl','Önceki izinler'),('new_acl','Yeni izinler')]:
            if getattr(entry,name):detail+='\n'+label+': '+getattr(entry,name)
        share=(entry.share_name or '—').replace('/','\\').rstrip('\\').split('\\')[-1]
        report.row([dt(entry.when),entry.who,ACTIONS.get(entry.action,entry.action),share,detail,entry.host])
    if not qs.exists():report.row(['Bu aralıkta kayıt yok.','','','','',''])
    return report.finish('Ufuk-FileAudit-Loglar-'+timezone.localtime().strftime('%Y%m%d-%H%M')+'.pdf')

def analytics_pdf(ctx,user):
    report=Report('Grafikler ve disk kullanım raporu',ctx['range_start'],ctx['range_end'],user)
    report.paragraph(f"Toplam işlem: {ctx['total']} · Silme: {ctx['deletes']} · Doğrulanan kopyalama: {ctx['copies']} · Yeni dosya/klasör: {ctx['creates']}")
    data=ctx['filter_form'].data
    filters=[label+': '+str(data[key]) for key,label in [('who','Kullanıcı'),('share_name','Paylaşım'),('action','İşlem'),('search','Arama'),('host','İstemci IP')] if data.get(key)]
    if filters:report.paragraph('Filtreler: '+' · '.join(filters))
    report.bars('En çok dosya silen kullanıcılar',ctx['top_deletes'])
    report.bars('En çok dosya kopyalayan kullanıcılar',ctx['top_copies'])
    report.paragraph('Kopyalama sayısı yalnızca sunucunun doğruladığı SMB kopyalama işlemleridir. İstemcinin okuyup yeniden yazarak yaptığı kopyalar, oluşturma/yazma kayıtlarında görünür.')
    report.bars('En çok yeni dosya oluşturan kullanıcılar',ctx['top_creates'])
    report.new_page();report.heading('Dosya sahibine göre disk kullanımı')
    snap=ctx['snapshot']
    if snap:
        report.paragraph('Ölçüm zamanı: '+dt(snap.completed_at)+f'. Taranan dosya: {snap.files}. Erişim hatası: {snap.errors}. Atlanan bağlantı: {snap.skipped}.')
        report.paragraph('Rapor bitiş tarihinden önce tamamlanan en son ölçüm kullanılır. Dosya sahibi, dosyayı son düzenleyen veya oluşturan kişiyle aynı olmayabilir. 1 GB = 1.073.741.824 bayt.')
        report.table([('Dosya sahibi',293),('Dosya sayısı',95),('Diskte ayrılan alan',140),('Dosya boyutları toplamı',160),('Ölçüm hatası',89.89)])
        for row in ctx['owners']:report.row([row['owner'],row['files'],gb(row['allocated_bytes']),gb(row['logical_bytes']),row['allocation_errors']])
        report.end_table()
        if snap.errors or snap.skipped:report.paragraph('Ölçüm kısmi olabilir: bazı dosyalara erişilemedi veya bağlantılar tarama dışında bırakıldı.')
    else:report.paragraph('Seçilen bitiş tarihinden önce tamamlanmış disk ölçümü yok. Geçmiş disk kullanımı geriye dönük oluşturulamaz.')
    report.heading('Günlük işlem özeti')
    report.table([('Tarih',388),('İşlem sayısı',389.89)])
    for row in ctx['timeline']:report.row([row['day'].strftime('%d.%m.%Y'),row['total']])
    if not ctx['timeline']:report.row(['Bu aralıkta kayıt yok.','0'])
    report.end_table()
    return report.finish('Ufuk-FileAudit-Rapor-'+timezone.localtime().strftime('%Y%m%d-%H%M')+'.pdf')
