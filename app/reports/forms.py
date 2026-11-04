from django import forms
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime,parse_date
from datetime import datetime,time,timedelta
import re
from .retention import cutoff

ACTIONS={'Created':'Oluşturuldu','Modified':'Değiştirildi','Accessed':'Okundu / erişildi','Renamed':'Yeniden adlandırıldı','Moved':'Taşındı','Removed':'Silindi','Copied':'Kopyalandı (doğrulandı)','Owner Changed':'Dosya sahibi değişti','ACL modified':'İzinler değişti'}
class Filters(forms.Form):
    start_date=forms.CharField(label='Başlangıç tarihi ve saati',required=False,widget=forms.TextInput(attrs={'placeholder':'GG.AA.YYYY SS:DD','data-audit-date':'true','autocomplete':'off'}))
    end_date=forms.CharField(label='Bitiş tarihi ve saati',required=False,widget=forms.TextInput(attrs={'placeholder':'GG.AA.YYYY SS:DD','data-audit-date':'true','autocomplete':'off'}))
    who=forms.CharField(label='Kullanıcı',required=False,max_length=200,widget=forms.TextInput(attrs={'placeholder':'Örn. DOMAIN\\kullanıcı'}))
    share_name=forms.ChoiceField(label='Paylaşım',required=False,choices=[('','Tüm paylaşımlar')])
    action=forms.ChoiceField(label='İşlem',required=False,choices=[('','Tüm işlemler'),*ACTIONS.items()])
    search=forms.CharField(label='Dosya veya klasör ara',required=False,max_length=500)
    host=forms.CharField(label='İstemci IP adresi',required=False,max_length=100)
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['share_name'].choices=[('','Tüm paylaşımlar')]+[(x,x) for x in settings.AUDIT_SHARES]

    def clean(self):
        data=super().clean();now=timezone.now();tz=timezone.get_current_timezone()
        for key,end in [('start_date',False),('end_date',True)]:
            value=data.get(key,'').strip()
            if not value:
                dt=now if end else timezone.localtime(now).replace(hour=0,minute=0,second=0,microsecond=0)
            else:
                try:
                    if re.match(r'^\d{2}\.\d{2}\.\d{4}',value):
                        dt=datetime.strptime(value,'%d.%m.%Y %H:%M')
                    elif len(value)==10:
                        date=parse_date(value)
                        dt=datetime.combine(date,time.max if end else time.min) if date else None
                    else:dt=parse_datetime(value)
                    if dt is None:raise ValueError()
                    if timezone.is_naive(dt):dt=timezone.make_aware(dt,tz)
                    if end and len(value)==16:dt+=timedelta(seconds=59,microseconds=999999)
                except (ValueError,TypeError,OverflowError):
                    self.add_error(key,'Geçerli bir tarih ve saat girin.');continue
            data[key+'_parsed']=dt
        start=data.get('start_date_parsed');end=data.get('end_date_parsed')
        if start and start<cutoff(now):self.add_error('start_date','En fazla son bir yıllık kayıtlar raporlanabilir.')
        if start and end and start>end:self.add_error('end_date','Bitiş, başlangıçtan önce olamaz.')
        return data
